from __future__ import annotations

import json

import pytest

from app.domain.errors import (
    AppError,
    ContextLengthError,
    ProviderAuthError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitError,
)
from app.domain.schemas import AnalysisResult
from app.prompts.analysis_prompt import build_repair_prompt, build_system_prompt, build_user_prompt
from app.providers.base import LLMMessage
from app.providers.mock_provider import MOCK_MODEL, MockProvider
from app.providers.mock_samples import (
    GENERAL_SAMPLE,
    MEETING_SAMPLE,
    PROJECT_BRIEF_SAMPLE,
    select_sample,
)
from app.services.json_extraction import JSONExtractionError, extract_json


# Builds the system and user messages for a document.
def msgs(text: str, title: str = "My Doc") -> list[LLMMessage]:
    return [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": build_user_prompt(title, text)},
    ]


# Provides a mock provider with no simulated latency.
@pytest.fixture
def provider() -> MockProvider:
    return MockProvider(latency_ms=0)


# Checks the default reply is valid JSON that includes the title.
def test_default_returns_valid_json_with_title(provider: MockProvider) -> None:
    response = provider.complete(msgs("quarterly report"), json_mode=True)
    assert response.model == MOCK_MODEL
    result = AnalysisResult.model_validate(json.loads(response.content))
    assert '"My Doc"' in result.summary


# Checks keywords in the text pick the matching sample.
@pytest.mark.parametrize(
    ("text", "sample"),
    [
        ("Meeting notes from Monday", MEETING_SAMPLE),
        ("Full transcript below", MEETING_SAMPLE),
        ("Attendees: Sam, Lee", MEETING_SAMPLE),
        ("Agenda item 1", MEETING_SAMPLE),
        ("Project brief v2", PROJECT_BRIEF_SAMPLE),
        ("The scope includes", PROJECT_BRIEF_SAMPLE),
        ("Requirements list", PROJECT_BRIEF_SAMPLE),
        ("Final deliverable", PROJECT_BRIEF_SAMPLE),
        ("Some random notes", GENERAL_SAMPLE),
    ],
)
def test_keyword_routing(text: str, sample: dict) -> None:
    assert select_sample(text) is sample


# Checks all samples are valid and one has no action items.
def test_samples_are_valid_and_one_has_no_action_items() -> None:
    samples = [MEETING_SAMPLE, PROJECT_BRIEF_SAMPLE, GENERAL_SAMPLE]
    for s in samples:
        result = AnalysisResult.model_validate(s)
        assert 4 <= len(result.key_points) <= 6
        assert 2 <= len(result.open_questions) <= 3
    assert any(not s["action_items"] for s in samples)


# Checks the fenced trigger wraps the JSON in a code fence.
def test_fenced(provider: MockProvider) -> None:
    content = provider.complete(msgs("x [[mock:fenced]]"), json_mode=True).content
    assert content.startswith("```json")
    assert extract_json(content)["summary"]


# Checks the malformed trigger fails even on repair.
def test_malformed_always(provider: MockProvider) -> None:
    m = msgs("x [[mock:malformed]]")
    with pytest.raises(JSONExtractionError):
        extract_json(provider.complete(m, json_mode=True).content)
    repair = [
        *m,
        {"role": "assistant", "content": "x"},
        {"role": "user", "content": build_repair_prompt("root: bad")},
    ]
    with pytest.raises(JSONExtractionError):
        extract_json(provider.complete(repair, json_mode=True).content)


# Checks the malformed_once trigger fails first and succeeds on repair.
def test_malformed_once(provider: MockProvider) -> None:
    m = msgs("x [[mock:malformed_once]]")
    with pytest.raises(JSONExtractionError):
        extract_json(provider.complete(m, json_mode=True).content)
    repair = [
        *m,
        {"role": "assistant", "content": "x"},
        {"role": "user", "content": build_repair_prompt("root: bad")},
    ]
    assert extract_json(provider.complete(repair, json_mode=True).content)


# Checks the invalid_schema trigger leaves out the summary.
def test_invalid_schema(provider: MockProvider) -> None:
    data = extract_json(provider.complete(msgs("[[mock:invalid_schema]]"), json_mode=True).content)
    assert "summary" not in data


# Checks each error trigger raises the matching error.
@pytest.mark.parametrize(
    ("token", "error"),
    [
        ("ratelimit", RateLimitError),
        ("timeout", ProviderTimeoutError),
        ("unavailable", ProviderUnavailableError),
        ("auth", ProviderAuthError),
        ("context", ContextLengthError),
    ],
)
def test_error_tokens(provider: MockProvider, token: str, error: type[AppError]) -> None:
    with pytest.raises(error) as exc:
        provider.complete(msgs(f"text [[mock:{token}]]"), json_mode=True)
    if token == "ratelimit":
        assert exc.value.retry_after_seconds == 2


# Checks the configured latency is passed to sleep.
def test_latency_sleep() -> None:
    delays: list[float] = []
    MockProvider(latency_ms=300, sleep=delays.append).complete(msgs("x"), json_mode=True)
    assert delays == [0.3]


# Checks raw messages without the prompt template still work.
def test_handles_messages_without_template(provider: MockProvider) -> None:
    response = provider.complete([{"role": "user", "content": "meeting"}], json_mode=False)
    assert '"Untitled"' in json.loads(response.content)["summary"]
