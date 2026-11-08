from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, Request

from app.config import Settings
from app.db.database import connect
from app.db.repository import AnalysisRepository
from app.domain.errors import AuthRequiredError
from app.domain.schemas import UserOut
from app.providers.base import LLMProvider
from app.services.analysis_service import AnalysisService
from app.services.auth_service import AuthService


# Returns the settings stored on the app.
def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


# Returns the LLM provider stored on the app.
def get_provider(request: Request) -> LLMProvider:
    return request.app.state.provider


# Opens a database connection for one request and closes it afterwards.
def get_connection(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> Iterator[sqlite3.Connection]:
    conn = connect(settings.DATABASE_PATH)
    try:
        yield conn
    finally:
        conn.close()


# Reads the bearer token from the Authorization header, or raises auth required.
def get_token(authorization: Annotated[str | None, Header()] = None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthRequiredError()
    return token.strip()


# Builds the auth service on the request's database connection.
def get_auth_service(
    conn: Annotated[sqlite3.Connection, Depends(get_connection)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> AuthService:
    return AuthService(conn, settings.SESSION_DAYS)


# Returns the user behind the request's token, or raises auth required.
def get_current_user(
    token: Annotated[str, Depends(get_token)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> UserOut:
    return auth.user_for_token(token)


# Wraps the request's database connection in a repository limited to the current user.
def get_repository(
    conn: Annotated[sqlite3.Connection, Depends(get_connection)],
    user: Annotated[UserOut, Depends(get_current_user)],
) -> AnalysisRepository:
    return AnalysisRepository(conn, user.id)


# Builds the analysis service, using a test sleep function if one is set on the app.
def get_service(
    request: Request,
    provider: Annotated[LLMProvider, Depends(get_provider)],
    repository: Annotated[AnalysisRepository, Depends(get_repository)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> AnalysisService:
    sleep = getattr(request.app.state, "sleep", None) or time.sleep
    return AnalysisService(provider, repository, settings, sleep=sleep)


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
ProviderDep = Annotated[LLMProvider, Depends(get_provider)]
ServiceDep = Annotated[AnalysisService, Depends(get_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
CurrentUserDep = Annotated[UserOut, Depends(get_current_user)]
TokenDep = Annotated[str, Depends(get_token)]
