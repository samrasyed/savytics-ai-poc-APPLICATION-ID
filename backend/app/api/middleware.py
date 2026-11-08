from __future__ import annotations

import json
import logging
import math
import re
import time
import uuid
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.domain.errors import AppError, InternalError, PayloadTooLargeError
from app.logging_config import request_id_var

logger = logging.getLogger("app.access")
error_logger = logging.getLogger("app.errors")

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9-]{1,64}$")


# Builds the standard JSON error envelope for an error.
def error_body(error: AppError, request_id: str, details: Any = None) -> dict[str, Any]:
    return {
        "error": {
            "code": error.code,
            "message": error.message,
            "retryable": error.retryable,
            "request_id": request_id,
            "details": details if details is not None else error.details,
        }
    }


# Returns a Retry-After header when the error carries a retry delay.
def error_headers(error: AppError) -> dict[str, str]:
    retry_after = getattr(error, "retry_after_seconds", None)
    if retry_after is not None:
        return {"Retry-After": str(max(1, math.ceil(retry_after)))}
    return {}


# Sends a complete JSON response directly over the raw ASGI channel.
async def _send_json(send: Send, status: int, body: dict[str, Any], headers: dict[str, str]):
    payload = json.dumps(body).encode()
    raw_headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(payload)).encode()),
        *[(k.lower().encode(), v.encode()) for k, v in headers.items()],
    ]
    await send({"type": "http.response.start", "status": status, "headers": raw_headers})
    await send({"type": "http.response.body", "body": payload})


class RequestIdMiddleware:
    # Stores the wrapped ASGI app.
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    # Reuses a valid incoming X-Request-ID or creates one, and echoes it in the response.
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = None
        for name, value in scope.get("headers", []):
            if name == b"x-request-id":
                incoming = value.decode("latin-1")
                break
        request_id = incoming if incoming and _REQUEST_ID_RE.match(incoming) else str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_var.set(request_id)

        # Adds the X-Request-ID header to the response start message.
        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)


class AccessLogMiddleware:
    # Stores the wrapped ASGI app.
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    # Logs method, path, status and duration for every HTTP request.
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        start = time.perf_counter()
        status_holder = {"status": 500}

        # Records the response status code as it is sent.
        async def capture(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, capture)
        finally:
            logger.info(
                "request method=%s path=%s status=%d duration_ms=%.1f",
                scope.get("method"),
                scope.get("path"),
                status_holder["status"],
                (time.perf_counter() - start) * 1000,
            )


class BodySizeLimitMiddleware:
    # Stores the wrapped ASGI app and the maximum allowed body size.
    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    # Rejects requests whose declared or streamed body is larger than the limit.
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    length = int(value)
                except ValueError:
                    length = 0
                if length > self.max_body_bytes:
                    error = PayloadTooLargeError()
                    await _send_json(
                        send, error.http_status, error_body(error, request_id_var.get()), {}
                    )
                    return
                break

        received = 0

        # Counts streamed body bytes and raises once the limit is exceeded.
        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body_bytes:
                    raise PayloadTooLargeError()
            return message

        await self.app(scope, limited_receive, send)


class UnhandledErrorMiddleware:
    # Stores the wrapped ASGI app.
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    # Turns any exception that escapes the app into the JSON error envelope.
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        # Remembers whether the response has already started.
        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception as exc:
            if started:
                raise
            if isinstance(exc, AppError):
                error: AppError = exc
            else:
                error_logger.exception("unhandled exception")
                error = InternalError()
            await _send_json(
                send,
                error.http_status,
                error_body(error, request_id_var.get()),
                error_headers(error),
            )
