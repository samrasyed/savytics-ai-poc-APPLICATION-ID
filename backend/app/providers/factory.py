from __future__ import annotations

from app.config import Settings
from app.providers.base import LLMProvider
from app.providers.mock_provider import MockProvider


# Creates the mock or OpenAI-compatible provider based on the settings.
def build_provider(settings: Settings) -> LLMProvider:
    if settings.LLM_PROVIDER == "mock":
        return MockProvider(latency_ms=settings.MOCK_LATENCY_MS)

    settings.validate_for_startup()
    from app.providers.openai_compatible import OpenAICompatibleProvider

    return OpenAICompatibleProvider(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY.get_secret_value(),
        model=settings.LLM_MODEL,
        timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
        temperature=settings.LLM_TEMPERATURE,
        max_output_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
        reasoning_effort=settings.LLM_REASONING_EFFORT or None,
    )
