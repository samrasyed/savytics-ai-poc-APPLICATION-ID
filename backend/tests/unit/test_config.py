from __future__ import annotations

import logging

import pytest

from app.config import ConfigurationError, Settings
from app.logging_config import RedactingFormatter, redact, register_secret
from app.providers.factory import build_provider
from app.providers.mock_provider import MockProvider
from app.providers.openai_compatible import OpenAICompatibleProvider


# Builds settings from keyword arguments, ignoring any .env file.
def make(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


# Checks the default settings use mock mode and pass startup validation.
def test_defaults_are_safe() -> None:
    s = make()
    assert s.LLM_PROVIDER == "mock"
    assert s.is_mock
    assert s.effective_model == "mock-analyzer-v1"
    assert s.cors_origins_list == ["http://localhost:5173"]
    s.validate_for_startup()


# Checks openai_compatible mode lists the missing key and model settings.
@pytest.mark.parametrize(
    ("kw", "missing"),
    [
        ({}, "LLM_API_KEY, LLM_MODEL"),
        ({"LLM_API_KEY": "k"}, "LLM_MODEL"),
        ({"LLM_MODEL": "m"}, "LLM_API_KEY"),
    ],
)
def test_openai_compatible_requires_key_and_model(kw: dict, missing: str) -> None:
    s = make(LLM_PROVIDER="openai_compatible", **kw)
    with pytest.raises(ConfigurationError, match=missing):
        s.validate_for_startup()


# Checks the API key never shows up in repr or error messages.
def test_key_not_in_repr_or_error() -> None:
    s = make(LLM_PROVIDER="openai_compatible", LLM_API_KEY="supersecretvalue")
    assert "supersecretvalue" not in repr(s)
    with pytest.raises(ConfigurationError) as exc:
        s.validate_for_startup()
    assert "supersecretvalue" not in str(exc.value)


# Checks the factory builds the right provider for each mode.
def test_factory() -> None:
    assert isinstance(build_provider(make(MOCK_LATENCY_MS=0)), MockProvider)
    p = build_provider(make(LLM_PROVIDER="openai_compatible", LLM_API_KEY="k" * 8, LLM_MODEL="m"))
    assert isinstance(p, OpenAICompatibleProvider)
    assert p.model == "m"
    with pytest.raises(ConfigurationError):
        build_provider(make(LLM_PROVIDER="openai_compatible"))


# Checks CORS origins are split and the log level is uppercased.
def test_cors_list_and_log_level() -> None:
    s = make(CORS_ORIGINS="http://a.test, http://b.test,", LOG_LEVEL="debug")
    assert s.cors_origins_list == ["http://a.test", "http://b.test"]
    assert s.LOG_LEVEL == "DEBUG"


# Checks registered secrets and bearer tokens are redacted.
def test_redaction() -> None:
    register_secret("my-very-secret-key")
    assert "my-very-secret-key" not in redact("key=my-very-secret-key")
    assert redact("Authorization: Bearer abc.def") == "Authorization: Bearer [REDACTED]"
    record = logging.LogRecord("x", logging.INFO, "f", 1, "k=%s", ("my-very-secret-key",), None)
    assert "my-very-secret-key" not in RedactingFormatter("%(message)s").format(record)
