from __future__ import annotations

from typing import Any


class AppError(Exception):
    code: str = "INTERNAL_ERROR"
    http_status: int = 500
    retryable: bool = False
    default_message: str = "Something went wrong on our side."

    # Stores the user-facing message and optional details for the error.
    def __init__(self, message: str | None = None, *, details: Any = None) -> None:
        self.message = message or self.default_message
        self.details = details
        super().__init__(self.message)

    # Shows the error class, code and message for debugging.
    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


class EmptyInputError(AppError):
    code = "EMPTY_INPUT"
    http_status = 422
    default_message = "Please enter a title and some text to analyze."


class InputTooLongError(AppError):
    code = "INPUT_TOO_LONG"
    http_status = 422

    # Builds a message saying which field is too long and by how much.
    def __init__(self, *, field: str, length: int, limit: int) -> None:
        noun = "title" if field == "title" else "text"
        super().__init__(
            f"The {noun} is {length} characters; the limit is {limit}. Please shorten it.",
            details={"field": field, "length": length, "limit": limit},
        )


class RequestInvalidError(AppError):
    code = "VALIDATION_ERROR"
    http_status = 422
    default_message = "The request is invalid."


class PayloadTooLargeError(AppError):
    code = "PAYLOAD_TOO_LARGE"
    http_status = 413
    default_message = "The request is too large."


class AnalysisNotFoundError(AppError):
    code = "NOT_FOUND"
    http_status = 404
    default_message = "That analysis does not exist."


class AuthRequiredError(AppError):
    code = "AUTH_REQUIRED"
    http_status = 401
    default_message = "Please log in to continue."


class InvalidCredentialsError(AppError):
    code = "INVALID_CREDENTIALS"
    http_status = 401
    default_message = "That email and password do not match an account."


class EmailTakenError(AppError):
    code = "EMAIL_TAKEN"
    http_status = 409
    default_message = "An account with that email already exists. Try logging in."


class ContextLengthError(AppError):
    code = "CONTEXT_TOO_LONG"
    http_status = 422
    default_message = "This document is too long for the AI model. Please shorten it."


class MalformedResponseError(AppError):
    code = "MALFORMED_AI_RESPONSE"
    http_status = 502
    retryable = True
    default_message = "The AI returned a result we could not read. Please try again."


class JsonGenerationError(MalformedResponseError):
    default_message = "The AI could not produce a readable result. Please try again."


class RateLimitError(AppError):
    code = "RATE_LIMITED"
    http_status = 429
    retryable = True
    default_message = "The AI service is busy. Please wait a moment and try again."

    # Stores how long the provider asked us to wait before retrying.
    def __init__(self, message: str | None = None, *, retry_after_seconds: float | None = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class ProviderTimeoutError(AppError):
    code = "PROVIDER_TIMEOUT"
    http_status = 504
    retryable = True
    default_message = "The analysis took too long. Please try again."


class ProviderUnavailableError(AppError):
    code = "PROVIDER_UNAVAILABLE"
    http_status = 503
    retryable = True
    default_message = "The AI service is unavailable right now. Please try again shortly."


class ProviderAuthError(AppError):
    code = "PROVIDER_AUTH_ERROR"
    http_status = 502
    default_message = (
        "The AI service is not configured correctly. Please contact the administrator."
    )


class ProviderRequestError(AppError):
    code = "PROVIDER_ERROR"
    http_status = 502
    default_message = "The AI service rejected the request."


class InternalError(AppError):
    code = "INTERNAL_ERROR"
    http_status = 500
    default_message = "Something went wrong on our side."


TRANSIENT_ERRORS: tuple[type[AppError], ...] = (
    JsonGenerationError,
    RateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
