from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.middleware import (
    AccessLogMiddleware,
    BodySizeLimitMiddleware,
    RequestIdMiddleware,
    UnhandledErrorMiddleware,
    error_body,
    error_headers,
)
from app.api.routes_analyses import router as analyses_router
from app.api.routes_auth import router as auth_router
from app.api.routes_health import router as health_router
from app.config import Settings, get_settings
from app.db.database import init_db
from app.domain.errors import AppError, InternalError, RequestInvalidError
from app.logging_config import configure_logging, register_secret, request_id_var
from app.prompts.analysis_prompt import PROMPT_VERSION
from app.providers.base import LLMProvider
from app.providers.factory import build_provider

logger = logging.getLogger(__name__)


class _HTTPError(AppError):
    # Builds an AppError from a plain HTTP status, code and message.
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.http_status = status
        self.code = code


_HTTP_CODES = {
    404: ("NOT_FOUND", "The requested resource does not exist."),
    405: ("METHOD_NOT_ALLOWED", "This method is not allowed for this resource."),
}


# Returns the request ID for the current request.
def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_var.get()


# Registers handlers that turn every error into the standard JSON error envelope.
def _install_exception_handlers(app: FastAPI) -> None:
    # Converts a domain error into its JSON error response.
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content=error_body(exc, _request_id(request)),
            headers=error_headers(exc),
        )

    # Converts request validation failures into a VALIDATION_ERROR response.
    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        details = [
            {
                "field": ".".join(str(p) for p in err.get("loc", ()) if p != "body") or "body",
                "reason": err.get("msg", "invalid value"),
            }
            for err in exc.errors()
        ]
        error = RequestInvalidError()
        return JSONResponse(
            status_code=error.http_status, content=error_body(error, _request_id(request), details)
        )

    # Converts HTTP errors (404, 405, wrapped body errors) into the JSON envelope.
    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc.__cause__, AppError):
            return await handle_app_error(request, exc.__cause__)
        code, message = _HTTP_CODES.get(exc.status_code, ("HTTP_ERROR", "The request failed."))
        error = _HTTPError(exc.status_code, code, message)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(error, _request_id(request)),
            headers=getattr(exc, "headers", None),
        )

    # Logs any unexpected exception and returns a generic INTERNAL_ERROR response.
    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled exception")
        error = InternalError()
        return JSONResponse(status_code=500, content=error_body(error, _request_id(request)))


# Builds the FastAPI app with its lifespan, middleware, error handlers and routes.
def create_app(settings: Settings | None = None, provider: LLMProvider | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.LOG_LEVEL)
    register_secret(settings.LLM_API_KEY.get_secret_value())
    register_secret(settings.DATABASE_URL.get_secret_value())

    # Validates config, prepares the database and creates the provider on startup.
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings.validate_for_startup()
        init_db(settings.database_target)
        app.state.provider = provider or build_provider(settings)
        logger.info(
            "startup provider=%s model=%s prompt_version=%s env=%s",
            app.state.provider.name,
            app.state.provider.model,
            PROMPT_VERSION,
            settings.APP_ENV,
        )
        yield

    app = FastAPI(
        title="AI Document Analyzer API",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings

    _install_exception_handlers(app)

    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(BodySizeLimitMiddleware, max_body_bytes=settings.MAX_BODY_BYTES)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After", "Location"],
    )

    app.include_router(auth_router)
    app.include_router(analyses_router)
    app.include_router(health_router)
    return app


# Creates the app using settings from the environment.
def _default_app() -> FastAPI:
    return create_app()


app = _default_app()
