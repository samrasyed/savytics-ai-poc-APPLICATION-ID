from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

import httpx
import pytest

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
from app.providers.openai_compatible import OpenAICompatibleProvider

API_KEY = "gsk_test_secret_key_123456"
MESSAGES: list[Any] = [{"role": "user", "content": "hi"}]


# Builds a fake chat-completion response body.
def completion(
    content: str | None = '{"summary": "ok"}', finish_reason: str = "stop", choices: bool = True
) -> dict[str, Any]:
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 0,
        "model": "llama-test",
        "choices": [
            {
                "index": 0,
                "finish_reason": finish_reason,
                "message": {"role": "assistant", "content": content},
            }
        ]
        if choices
        else [],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
    }


# Builds a fake provider error body.
def error_body(message: str, type_: str = "invalid_request_error") -> dict[str, Any]:
    return {"error": {"message": message, "type": type_}}


# Creates a provider whose HTTP calls go to the given handler.
def make_provider(handler: Callable[[httpx.Request], httpx.Response]) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        base_url="https://llm.test/v1",
        api_key=API_KEY,
        model="llama-test",
        timeout_seconds=5,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


# Checks a successful reply is mapped and the request is well formed.
def test_success_maps_response() -> None:
    seen: list[dict[str, Any]] = []

    # Records the request, checks its URL and headers, and returns a success.
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == f"Bearer {API_KEY}"
        return httpx.Response(200, json=completion())

    resp = make_provider(handler).complete(MESSAGES, json_mode=True)
    assert resp.content == '{"summary": "ok"}'
    assert resp.model == "llama-test"
    assert (resp.prompt_tokens, resp.completion_tokens) == (11, 7)
    assert seen[0]["response_format"] == {"type": "json_object"}
    assert seen[0]["temperature"] == 0.2
    assert seen[0]["max_tokens"] == 2048


# Checks JSON mode off sends no response_format field.
def test_json_mode_off_sends_no_response_format() -> None:
    seen: list[dict[str, Any]] = []

    # Records the request and returns a success.
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=completion())

    make_provider(handler).complete(MESSAGES, json_mode=False)
    assert "response_format" not in seen[0]


# Checks a 429 with retry-after becomes RateLimitError with that delay.
def test_429_with_retry_after() -> None:
    provider = make_provider(
        lambda r: httpx.Response(429, headers={"retry-after": "7"}, json=error_body("slow down"))
    )
    with pytest.raises(RateLimitError) as exc:
        provider.complete(MESSAGES, json_mode=True)
    assert exc.value.retry_after_seconds == 7


# Checks retry-after-ms is read and a missing header gives no delay.
def test_429_with_retry_after_ms_and_without_header() -> None:
    provider = make_provider(
        lambda r: httpx.Response(429, headers={"retry-after-ms": "1500"}, json=error_body("x"))
    )
    with pytest.raises(RateLimitError) as exc:
        provider.complete(MESSAGES, json_mode=True)
    assert exc.value.retry_after_seconds == 1.5

    provider = make_provider(lambda r: httpx.Response(429, json=error_body("x")))
    with pytest.raises(RateLimitError) as exc:
        provider.complete(MESSAGES, json_mode=True)
    assert exc.value.retry_after_seconds is None


# Checks each HTTP status maps to the right domain error.
@pytest.mark.parametrize(
    ("status", "body", "error"),
    [
        (401, error_body("Invalid API Key"), ProviderAuthError),
        (403, error_body("forbidden"), ProviderAuthError),
        (
            400,
            error_body("Please reduce the length of the messages: maximum context length"),
            ContextLengthError,
        ),
        (413, error_body("Request too large: too many tokens"), ContextLengthError),
        (
            413,
            error_body(
                "Request too large for model on tokens per minute (TPM): Limit 8000, "
                "Requested 9100, please reduce your message size and try again."
            ),
            ContextLengthError,
        ),
        (
            400,
            {
                "error": {
                    "message": "Failed to generate JSON. Please adjust your prompt.",
                    "type": "invalid_request_error",
                    "code": "json_validate_failed",
                    "failed_generation": '{"reasoning": "response_format',
                }
            },
            JsonGenerationError,
        ),
        (400, error_body("bad temperature"), ProviderRequestError),
        (404, error_body("model `x` does not exist"), ProviderRequestError),
        (422, error_body("unprocessable"), ProviderRequestError),
        (500, error_body("internal"), ProviderUnavailableError),
        (503, error_body("overloaded"), ProviderUnavailableError),
    ],
)
def test_status_mapping(status: int, body: dict[str, Any], error: type[AppError]) -> None:
    provider = make_provider(lambda r: httpx.Response(status, json=body))
    with pytest.raises(error):
        provider.complete(MESSAGES, json_mode=True)


# Checks a rejected response_format falls back once and is remembered.
def test_response_format_rejected_then_success_and_remembered() -> None:
    seen: list[dict[str, Any]] = []

    # Rejects response_format requests and accepts plain ones.
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen.append(payload)
        if "response_format" in payload:
            return httpx.Response(400, json=error_body("response_format is not supported"))
        return httpx.Response(200, json=completion())

    provider = make_provider(handler)
    assert provider.complete(MESSAGES, json_mode=True).content
    assert provider.complete(MESSAGES, json_mode=True).content
    assert ["response_format" in s for s in seen] == [True, False, False]


# Checks a failure during the JSON-mode fallback is still mapped.
def test_response_format_fallback_failure_is_mapped() -> None:
    # Rejects response_format and then fails the fallback call.
    def handler(request: httpx.Request) -> httpx.Response:
        if "response_format" in json.loads(request.content):
            return httpx.Response(400, json=error_body("response_format unsupported"))
        return httpx.Response(503, json=error_body("down"))

    with pytest.raises(ProviderUnavailableError):
        make_provider(handler).complete(MESSAGES, json_mode=True)


# Checks an HTTP timeout becomes ProviderTimeoutError.
def test_timeout() -> None:
    # Simulates a read timeout.
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(ProviderTimeoutError):
        make_provider(handler).complete(MESSAGES, json_mode=True)


# Checks a connection failure becomes ProviderUnavailableError.
def test_connection_error() -> None:
    # Simulates a refused connection.
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(ProviderUnavailableError):
        make_provider(handler).complete(MESSAGES, json_mode=True)


# Checks a reply cut off by the token limit is flagged as truncated.
def test_finish_reason_length_is_flagged() -> None:
    provider = make_provider(
        lambda r: httpx.Response(200, json=completion('{"summary": "cut', finish_reason="length"))
    )
    resp = provider.complete(MESSAGES, json_mode=True)
    assert resp.truncated
    assert resp.content == '{"summary": "cut'


# Checks empty or missing content raises MalformedResponseError.
@pytest.mark.parametrize(
    "payload", [completion(choices=False), completion(content=None), completion(content="   ")]
)
def test_empty_content_is_malformed(payload: dict[str, Any]) -> None:
    provider = make_provider(lambda r: httpx.Response(200, json=payload))
    with pytest.raises(MalformedResponseError):
        provider.complete(MESSAGES, json_mode=True)


# Checks the API key is redacted from provider error logs.
def test_api_key_is_redacted_in_logs(caplog: pytest.LogCaptureFixture) -> None:
    from app.logging_config import RedactingFormatter

    provider = make_provider(
        lambda r: httpx.Response(401, json=error_body(f"Invalid API Key {API_KEY}"))
    )
    with caplog.at_level(logging.WARNING), pytest.raises(ProviderAuthError) as exc:
        provider.complete(MESSAGES, json_mode=True)
    formatter = RedactingFormatter("%(message)s")
    rendered = "\n".join(formatter.format(r) for r in caplog.records)
    assert API_KEY not in rendered
    assert API_KEY not in caplog.text
    assert API_KEY not in exc.value.message
    assert API_KEY not in repr(provider)


# Creates a provider with a reasoning effort whose HTTP calls go to the given handler.
def make_reasoning_provider(handler: Callable[[httpx.Request], httpx.Response]):
    return OpenAICompatibleProvider(
        base_url="https://llm.test/v1",
        api_key=API_KEY,
        model="gpt-oss-test",
        reasoning_effort="low",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


# Checks the reasoning effort is sent when configured.
def test_reasoning_effort_is_sent() -> None:
    seen: list[dict[str, Any]] = []

    # Records the request and returns a success.
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=completion())

    make_reasoning_provider(handler).complete(MESSAGES, json_mode=True)
    assert seen[0]["reasoning_effort"] == "low"
    make_provider(handler).complete(MESSAGES, json_mode=True)
    assert "reasoning_effort" not in seen[1]


# Checks a rejected reasoning effort is dropped, retried without it, and remembered.
def test_reasoning_effort_rejected_then_disabled() -> None:
    seen: list[dict[str, Any]] = []

    # Rejects requests that include reasoning_effort and accepts the rest.
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen.append(payload)
        if "reasoning_effort" in payload:
            return httpx.Response(400, json=error_body("reasoning_effort is not supported"))
        return httpx.Response(200, json=completion())

    provider = make_reasoning_provider(handler)
    provider.complete(MESSAGES, json_mode=True)
    provider.complete(MESSAGES, json_mode=True)
    assert ["reasoning_effort" in p for p in seen] == [True, False, False]
