from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response, status

from app.api.dependencies import AuthServiceDep, CurrentUserDep, TokenDep
from app.domain.schemas import AuthResponse, CredentialsRequest, ErrorResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


# Builds the OpenAPI error-response entries for the given status codes.
def _errors(*codes: int) -> dict[int | str, dict[str, Any]]:
    return {code: {"model": ErrorResponse} for code in codes}


# Creates an account and returns a session token for it.
@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=AuthResponse,
    responses=_errors(409, 422, 500),
    summary="Create an account",
)
def register(body: CredentialsRequest, auth: AuthServiceDep) -> AuthResponse:
    return auth.register(body.email, body.password)


# Logs in with email and password and returns a session token.
@router.post(
    "/login",
    response_model=AuthResponse,
    responses=_errors(401, 422, 500),
    summary="Log in",
)
def login(body: CredentialsRequest, auth: AuthServiceDep) -> AuthResponse:
    return auth.login(body.email, body.password)


# Returns the logged-in user.
@router.get("/me", response_model=UserOut, responses=_errors(401), summary="Current user")
def me(user: CurrentUserDep) -> UserOut:
    return user


# Ends the current session.
@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=_errors(401),
    summary="Log out",
)
def logout(user: CurrentUserDep, token: TokenDep, auth: AuthServiceDep) -> Response:
    auth.logout(token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
