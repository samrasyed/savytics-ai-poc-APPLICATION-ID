from __future__ import annotations

import logging
from typing import Any

import httpx
import openai

from app.domain.errors import (
    AppError,
    ContextLengthError,
    JsonGenerationError,
    MalformedResponseError,
    ProviderAuthError,
    ProviderRequestError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitError,
)
from app.logging_config import redact, register_secret
from app.providers.base import LLMMessage, ProviderResponse

logger = logging.getLogger(__name__)

_CONTEXT_MARKERS = (
    "context length",
    "context_length",
    "context window",
    "maximum context",
    "max tokens",
    "maximum tokens",
    "max_tokens",
    "too many tokens",
    "reduce the length",
    "prompt is too long",
    "request too large",
    "tokens per minute",
    "reduce your message size",
)

# Markers of the provider rejecting its own invalid JSON output (Groq: json_validate_failed).
_JSON_GENERATION_MARKERS = ("json_validate_failed", "failed to generate json")


# Collects the error message and body from an API error into one string.
def _error_text(exc: openai.APIStatusError) -> str:
    parts = [str(getattr(exc, "message", "") or "")]
    body = getattr(exc, "body", None)
    if body is not None:
        parts.append(str(body))
    return " ".join(parts)


# Reads the retry delay in seconds from the retry-after-ms or retry-after header.
def _parse_retry_after(headers: httpx.Headers | None) -> float | None:
    if not headers:
        return None
    ms = headers.get("retry-after-ms")
    if ms:
        try:
            return max(float(ms) / 1000, 0.0)
        except ValueError:
            pass
    value = headers.get("retry-after")
    if value:
        try:
            return max(float(value), 0.0)
        except ValueError:
            return None
    return None


class OpenAICompatibleProvider:
    name = "openai_compatible"

    # Creates the OpenAI client with SDK retries off, since the service handles retries.
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
        temperature: float = 0.2,
        max_output_tokens: int = 2048,
        reasoning_effort: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        register_secret(api_key)
        self.model = model
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._json_mode_supported = True
        self._reasoning_effort = reasoning_effort or None
        self._client = openai.OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=0,
            http_client=http_client,
        )

    # Shows the provider and model without exposing the API key.
    def __repr__(self) -> str:
        return f"OpenAICompatibleProvider(model={self.model!r})"

    # Calls the model, dropping options the provider rejects, and maps SDK errors.
    def complete(self, messages: list[LLMMessage], *, json_mode: bool) -> ProviderResponse:
        use_json = json_mode and self._json_mode_supported
        try:
            return self._create(messages, use_json)
        except openai.BadRequestError as exc:
            text = _error_text(exc).lower()
            if any(marker in text for marker in _JSON_GENERATION_MARKERS):
                raise self._map_error(exc) from None
            if self._reasoning_effort and "reasoning" in text:
                logger.warning("provider rejected reasoning_effort; disabling it for this process")
                self._reasoning_effort = None
                return self.complete(messages, json_mode=json_mode)
            if use_json and "response_format" in text:
                logger.warning(
                    "provider rejected response_format; disabling JSON mode for this process"
                )
                self._json_mode_supported = False
                try:
                    return self._create(messages, False)
                except openai.OpenAIError as exc2:
                    raise self._map_error(exc2) from None
            raise self._map_error(exc) from None
        except openai.OpenAIError as exc:
            raise self._map_error(exc) from None

    # Sends one chat-completion request and checks the reply has usable content.
    def _create(self, messages: list[LLMMessage], json_mode: bool) -> ProviderResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": self._max_output_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if self._reasoning_effort:
            kwargs["reasoning_effort"] = self._reasoning_effort
        completion = self._client.chat.completions.create(**kwargs)

        choices = getattr(completion, "choices", None) or []
        if not choices:
            raise MalformedResponseError(details={"reason": "no choices"})
        choice = choices[0]
        content = choice.message.content if choice.message else None
        if not content or not content.strip():
            raise MalformedResponseError(details={"reason": "empty content"})

        usage = getattr(completion, "usage", None)
        if choice.finish_reason == "length":
            logger.warning("provider output truncated (finish_reason=length)")
        return ProviderResponse(
            content=content,
            model=getattr(completion, "model", None) or self.model,
            finish_reason=choice.finish_reason,
            prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
            completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
        )

    # Translates an OpenAI SDK exception into the matching domain error.
    def _map_error(self, exc: Exception) -> AppError:
        if isinstance(exc, AppError):
            return exc
        if isinstance(exc, openai.APITimeoutError):
            logger.warning("provider timeout")
            return ProviderTimeoutError()
        if isinstance(exc, openai.APIConnectionError):
            logger.warning("provider connection error: %s", redact(str(exc)))
            return ProviderUnavailableError()
        if isinstance(exc, openai.APIStatusError):
            text = _error_text(exc)
            logger.warning("provider error status=%s body=%s", exc.status_code, redact(text)[:1000])
            if isinstance(exc, openai.RateLimitError) or exc.status_code == 429:
                return RateLimitError(retry_after_seconds=_parse_retry_after(exc.response.headers))
            if isinstance(exc, (openai.AuthenticationError, openai.PermissionDeniedError)):
                return ProviderAuthError()
            if isinstance(exc, openai.BadRequestError) or exc.status_code == 413:
                if any(marker in text.lower() for marker in _JSON_GENERATION_MARKERS):
                    return JsonGenerationError()
                if any(marker in text.lower() for marker in _CONTEXT_MARKERS):
                    return ContextLengthError()
                return ProviderRequestError()
            if exc.status_code >= 500:
                return ProviderUnavailableError()
            return ProviderRequestError()
        logger.warning("provider unexpected error type=%s", type(exc).__name__)
        return ProviderRequestError()
