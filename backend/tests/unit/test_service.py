from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.config import Settings
from app.db.repository import AnalysisRepository
from app.domain.errors import (
    AnalysisNotFoundError,
    EmptyInputError,
    InputTooLongError,
    JsonGenerationError,
    MalformedResponseError,
    ProviderAuthError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitError,
)
from app.domain.schemas import AnalyzeRequest
from app.prompts.analysis_prompt import PROMPT_VERSION, REPAIR_MARKER
from app.providers.base import ProviderResponse
from app.services.analysis_service import AnalysisService, normalize_text
from tests.conftest import FakeProvider, RecordingSleep, valid_json


class FakeClock:
    # Starts the fake clock at zero.
    def __init__(self) -> None:
        self.t = 0.0

    # Returns the current fake time.
    def __call__(self) -> float:
        return self.t


# Builds a service with a scripted fake provider and a sleep that advances the clock.
def make_service(
    script: list[Any],
    settings: Settings,
    repository: AnalysisRepository,
    sleep: RecordingSleep,
    clock: FakeClock | None = None,
) -> tuple[AnalysisService, FakeProvider]:
    provider = FakeProvider(script)
    clock = clock or FakeClock()

    # Records the delay and moves the fake clock forward by it.
    def advancing_sleep(seconds: float) -> None:
        sleep(seconds)
        clock.t += seconds

    service = AnalysisService(
        provider,
        repository,
        settings,
        sleep=advancing_sleep,
        clock=clock,
        now=lambda: datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        jitter=lambda: 0.1,
    )
    return service, provider


REQ = AnalyzeRequest(title="Sprint planning", text="Priya will draft pricing by Friday.")


# Provides a factory that builds services with optional setting overrides.
@pytest.fixture
def svc_factory(settings: Settings, repository: AnalysisRepository, sleep: RecordingSleep):
    # Builds a service for the given script, clock and setting overrides.
    def factory(script: list[Any], clock: FakeClock | None = None, **overrides: Any):
        overrides.setdefault("LLM_ENABLE_INTELLIGENCE", False)
        s = settings.model_copy(update=overrides)
        return make_service(script, s, repository, sleep, clock)

    return factory


# Checks a valid first reply is saved with one call in JSON mode.
def test_success_first_try(svc_factory, repository: AnalysisRepository) -> None:
    service, provider = svc_factory([valid_json()])
    record = service.analyze(REQ)
    assert len(provider.calls) == 1
    assert provider.json_modes == [True]
    assert record.result.action_items[0].owner == "Priya"
    assert repository.get(record.id) == record
    messages = provider.calls[0]
    assert messages[0]["role"] == "system"
    assert "<document>\nPriya will draft pricing by Friday.\n</document>" in messages[1]["content"]


# Checks a fenced JSON reply succeeds without a repair.
def test_fenced_output_succeeds(svc_factory) -> None:
    service, provider = svc_factory(["```json\n" + valid_json() + "\n```"])
    assert service.analyze(REQ).result.summary
    assert len(provider.calls) == 1


# Checks a malformed reply triggers one repair that succeeds.
def test_malformed_then_valid_uses_repair(svc_factory) -> None:
    service, provider = svc_factory(["not json at all", valid_json()])
    record = service.analyze(REQ)
    assert record.result.summary
    assert len(provider.calls) == 2
    repair_call = provider.calls[1]
    assert [m["role"] for m in repair_call] == ["system", "user", "assistant", "user"]
    assert repair_call[2]["content"] == "not json at all"
    assert REPAIR_MARKER in repair_call[3]["content"]
    assert "no JSON object found" in repair_call[3]["content"]


# Checks two malformed replies raise and log the raw output.
def test_malformed_twice_raises(svc_factory, caplog: pytest.LogCaptureFixture) -> None:
    service, provider = svc_factory(["garbage", "still garbage"])
    with pytest.raises(MalformedResponseError):
        service.analyze(REQ)
    assert len(provider.calls) == 2
    assert "still garbage" in caplog.text


# Checks a schema error is described in the repair prompt.
def test_invalid_schema_triggers_repair(svc_factory) -> None:
    service, provider = svc_factory(['{"key_points": []}', valid_json()])
    service.analyze(REQ)
    assert "summary: Field required" in provider.calls[1][3]["content"]


# Checks the bad reply echoed in the repair prompt is truncated.
def test_repair_echo_is_truncated(svc_factory) -> None:
    service, provider = svc_factory(["x" * 10_000, valid_json()])
    service.analyze(REQ)
    assert len(provider.calls[1][2]["content"]) == 4000


# Checks no repair is attempted when repairs are disabled.
def test_no_repair_when_disabled(svc_factory) -> None:
    service, provider = svc_factory(["garbage"], LLM_MAX_REPAIR_ATTEMPTS=0)
    with pytest.raises(MalformedResponseError):
        service.analyze(REQ)
    assert len(provider.calls) == 1


# Checks a rate limit is retried and then succeeds.
def test_rate_limit_then_success(svc_factory, sleep: RecordingSleep) -> None:
    service, provider = svc_factory([RateLimitError(), valid_json()])
    service.analyze(REQ)
    assert len(provider.calls) == 2
    assert sleep.delays == [pytest.approx(1.1)]


# Checks backoff delays double between retries.
def test_backoff_is_exponential(svc_factory, sleep: RecordingSleep) -> None:
    service, _ = svc_factory([ProviderUnavailableError(), ProviderUnavailableError(), valid_json()])
    service.analyze(REQ)
    assert sleep.delays == [pytest.approx(1.1), pytest.approx(2.1)]


# Checks repeated rate limits stop after the retry limit.
def test_rate_limit_every_time(svc_factory, settings: Settings) -> None:
    script = [RateLimitError() for _ in range(5)]
    service, provider = svc_factory(script)
    with pytest.raises(RateLimitError):
        service.analyze(REQ)
    assert len(provider.calls) == 1 + settings.LLM_MAX_TRANSIENT_RETRIES


# Checks the provider's retry-after delay is used.
def test_retry_after_is_honoured(svc_factory, sleep: RecordingSleep) -> None:
    service, _ = svc_factory([RateLimitError(retry_after_seconds=3), valid_json()])
    service.analyze(REQ)
    assert sleep.delays == [3]


# Checks a retry-after over 10 seconds is not retried.
def test_retry_after_over_10s_not_retried(svc_factory, sleep: RecordingSleep) -> None:
    service, provider = svc_factory([RateLimitError(retry_after_seconds=30), valid_json()])
    with pytest.raises(RateLimitError):
        service.analyze(REQ)
    assert len(provider.calls) == 1
    assert sleep.delays == []


# Checks timeouts are retried and then raised.
def test_timeout_retried_then_raised(svc_factory) -> None:
    service, provider = svc_factory([ProviderTimeoutError()] * 3)
    with pytest.raises(ProviderTimeoutError):
        service.analyze(REQ)
    assert len(provider.calls) == 3


# Checks no retry happens when it would exceed the time budget.
def test_budget_prevents_retry(svc_factory, sleep: RecordingSleep) -> None:
    clock = FakeClock()
    service, provider = svc_factory([ProviderTimeoutError(), valid_json()], clock=clock)
    original = provider.complete

    # Uses up almost the whole time budget before replying.
    def complete(messages, *, json_mode):
        clock.t += 89.5
        return original(messages, json_mode=json_mode)

    provider.complete = complete
    with pytest.raises(ProviderTimeoutError):
        service.analyze(REQ)
    assert sleep.delays == []


# Checks auth errors are not retried.
def test_auth_error_not_retried(svc_factory) -> None:
    service, provider = svc_factory([ProviderAuthError(), valid_json()])
    with pytest.raises(ProviderAuthError):
        service.analyze(REQ)
    assert len(provider.calls) == 1


# Checks empty input is rejected without calling the provider.
@pytest.mark.parametrize(
    ("title", "text"), [("", "text"), ("   ", "text"), ("Title", ""), ("Title", " \n\r\n ")]
)
def test_empty_input(svc_factory, title: str, text: str) -> None:
    service, provider = svc_factory([])
    with pytest.raises(EmptyInputError):
        service.analyze(AnalyzeRequest(title=title, text=text))
    assert provider.calls == []


# Checks text over the limit is rejected with details.
def test_too_long_text(svc_factory) -> None:
    service, _ = svc_factory([], MAX_INPUT_CHARS=10)
    with pytest.raises(InputTooLongError) as exc:
        service.analyze(AnalyzeRequest(title="t", text="x" * 11))
    assert "11" in exc.value.message and "10" in exc.value.message


# Checks a title over the limit is rejected.
def test_too_long_title(svc_factory) -> None:
    service, _ = svc_factory([], MAX_TITLE_CHARS=5)
    with pytest.raises(InputTooLongError, match="title"):
        service.analyze(AnalyzeRequest(title="abcdefg", text="x"))


# Checks the saved record has the right metadata and latency.
def test_saved_record_metadata(svc_factory, repository: AnalysisRepository) -> None:
    clock = FakeClock()
    service, provider = svc_factory([valid_json()], clock=clock)
    original = provider.complete

    # Advances the fake clock by 250 ms before replying.
    def complete(messages, *, json_mode):
        clock.t += 0.25
        return original(messages, json_mode=json_mode)

    provider.complete = complete
    record = service.analyze(REQ)
    assert record.provider == "fake"
    assert record.model == "fake-model"
    assert record.prompt_version == PROMPT_VERSION
    assert record.latency_ms == 250
    assert record.created_at == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert repository.get(record.id) == record


# Checks a reply cut off by the token limit is treated as malformed.
def test_truncated_output_treated_as_malformed(svc_factory) -> None:
    cut = ProviderResponse(
        content='{"summary": "abc',
        model="m",
        finish_reason="length",
        prompt_tokens=None,
        completion_tokens=None,
    )
    service, _ = svc_factory([cut, cut])
    with pytest.raises(MalformedResponseError):
        service.analyze(REQ)


# Checks line endings are unified and blank runs collapsed.
def test_normalize_text() -> None:
    assert normalize_text("  a\r\nb\n\n\n\n\n\nc  ") == "a\nb\n\n\nc"
    assert normalize_text("a\n \n\t\n \n \nb") == "a\n\n\nb"


# Checks get, list and delete work on saved analyses.
def test_get_list_delete(svc_factory) -> None:
    service, _ = svc_factory([valid_json(), valid_json()])
    first = service.analyze(REQ)
    second = service.analyze(REQ)
    assert service.get(first.id).id == first.id
    listing = service.list(10, 0)
    assert listing.total == 2
    assert {i.id for i in listing.items} == {first.id, second.id}
    service.delete(first.id)
    with pytest.raises(AnalysisNotFoundError):
        service.get(first.id)
    with pytest.raises(AnalysisNotFoundError):
        service.delete(first.id)
    with pytest.raises(AnalysisNotFoundError):
        service.get("not-a-uuid")


# Checks the saved model name comes from the reply that was actually used after a repair.
def test_model_comes_from_final_response(svc_factory) -> None:
    final = ProviderResponse(
        content=valid_json(),
        model="repaired-model",
        finish_reason="stop",
        prompt_tokens=None,
        completion_tokens=None,
    )
    service, _ = svc_factory(["garbage", final])
    assert service.analyze(REQ).model == "repaired-model"


INTEL_OK = (
    '{"contradictions": [], '
    '"risks": [{"description": "Pricing may slip", '
    '"evidence": "Priya will draft pricing by Friday"}], '
    '"dependencies": []}'
)


# Checks the intelligence pass runs after extraction and its results are validated and saved.
def test_intelligence_pass_runs(svc_factory, repository: AnalysisRepository) -> None:
    service, provider = svc_factory([valid_json(), INTEL_OK], LLM_ENABLE_INTELLIGENCE=True)
    record = service.analyze(REQ)
    assert len(provider.calls) == 2
    assert "consistency and risk analyst" in provider.calls[1][0]["content"]
    intel = record.result.intelligence
    assert intel.status == "complete"
    assert intel.modules == {"contradictions": "ok", "risks": "ok", "dependencies": "ok"}
    assert record.result.risks[0].evidence_status == "verified"
    assert repository.get(record.id) == record


# Checks a failed intelligence pass still saves the extraction with a failed status.
def test_intelligence_failure_is_contained(svc_factory) -> None:
    service, _ = svc_factory(
        [valid_json(), "garbage", "still garbage"], LLM_ENABLE_INTELLIGENCE=True
    )
    record = service.analyze(REQ)
    assert record.result.summary
    assert record.result.intelligence.status == "failed"
    assert record.result.intelligence.message
    assert record.result.risks == []


# Checks a provider error in the intelligence pass does not fail the analysis.
def test_intelligence_provider_error_is_contained(svc_factory) -> None:
    service, _ = svc_factory([valid_json(), ProviderAuthError()], LLM_ENABLE_INTELLIGENCE=True)
    assert service.analyze(REQ).result.intelligence.status == "failed"


# Checks one broken module section does not affect the other modules.
def test_one_module_failure_gives_partial_status(svc_factory) -> None:
    bad = '{"contradictions": "oops", "risks": [], "dependencies": []}'
    service, _ = svc_factory([valid_json(), bad], LLM_ENABLE_INTELLIGENCE=True)
    intel = service.analyze(REQ).result.intelligence
    assert intel.status == "partial"
    assert intel.modules["contradictions"] == "failed"
    assert intel.modules["risks"] == "ok"


# Checks every module failing gives an overall failed status.
def test_all_modules_failing_gives_failed_status(svc_factory) -> None:
    bad = '{"contradictions": 1, "risks": 2, "dependencies": 3}'
    service, _ = svc_factory([valid_json(), bad], LLM_ENABLE_INTELLIGENCE=True)
    assert service.analyze(REQ).result.intelligence.status == "failed"


# Checks disabling intelligence skips the second call but still validates the result.
def test_intelligence_disabled(svc_factory) -> None:
    service, provider = svc_factory([valid_json()])
    record = service.analyze(REQ)
    assert len(provider.calls) == 1
    assert record.result.intelligence.status == "disabled"
    assert record.result.validation.checks


# Checks earlier analyses are sent as cross-document context.
def test_previous_documents_are_compared(svc_factory) -> None:
    service, provider = svc_factory(
        [valid_json(), INTEL_OK, valid_json(), INTEL_OK], LLM_ENABLE_INTELLIGENCE=True
    )
    service.analyze(AnalyzeRequest(title="First doc", text="Priya will draft pricing by Friday."))
    second = service.analyze(REQ)
    assert second.result.intelligence.documents_compared == 1
    assert "[D1] Title: First doc" in provider.calls[3][1]["content"]


# Checks no earlier documents are sent when the context limit is zero.
def test_cross_doc_limit_zero(svc_factory) -> None:
    service, provider = svc_factory(
        [valid_json(), INTEL_OK, valid_json(), INTEL_OK],
        LLM_ENABLE_INTELLIGENCE=True,
        CROSS_DOC_CONTEXT_LIMIT=0,
    )
    service.analyze(REQ)
    assert service.analyze(REQ).result.intelligence.documents_compared == 0
    assert "(no previous documents)" in provider.calls[3][1]["content"]


# Checks re-running intelligence updates the stored analysis.
def test_rerun_intelligence_updates_record(svc_factory, repository: AnalysisRepository) -> None:
    service, provider = svc_factory(
        [valid_json(), "garbage", "garbage", INTEL_OK], LLM_ENABLE_INTELLIGENCE=True
    )
    record = service.analyze(REQ)
    assert record.result.intelligence.status == "failed"
    updated = service.rerun_intelligence(record.id)
    assert updated.result.intelligence.status == "complete"
    assert len(updated.result.risks) == 1
    assert repository.get(record.id).result == updated.result
    assert len(provider.calls) == 4


# Checks a failing re-run raises the error and leaves the stored analysis unchanged.
def test_rerun_intelligence_failure_raises(svc_factory, repository: AnalysisRepository) -> None:
    service, _ = svc_factory(
        [valid_json(), INTEL_OK, ProviderAuthError()], LLM_ENABLE_INTELLIGENCE=True
    )
    record = service.analyze(REQ)
    with pytest.raises(ProviderAuthError):
        service.rerun_intelligence(record.id)
    assert repository.get(record.id) == record


# Checks re-running intelligence on an unknown ID raises NOT_FOUND.
def test_rerun_unknown_id(svc_factory) -> None:
    service, _ = svc_factory([])
    with pytest.raises(AnalysisNotFoundError):
        service.rerun_intelligence("not-a-uuid")


# Checks a longer retry-after is honoured when the configured cap allows it.
def test_retry_after_cap_is_configurable(svc_factory, sleep: RecordingSleep) -> None:
    service, _ = svc_factory(
        [RateLimitError(retry_after_seconds=25), valid_json()], LLM_MAX_RETRY_AFTER_SECONDS=30
    )
    service.analyze(REQ)
    assert sleep.delays == [25]


# Checks a provider-side JSON generation failure is retried like a transient error.
def test_json_generation_failure_is_retried(
    settings: Settings, repository: AnalysisRepository, sleep: RecordingSleep
) -> None:
    script = [
        JsonGenerationError(),
        valid_json(),
        '{"contradictions": [], "risks": [], "dependencies": []}',
    ]
    service, provider = make_service(script, settings, repository, sleep)
    record = service.analyze(AnalyzeRequest(title="T", text="Priya will draft pricing by Friday."))
    assert record.result.summary
    assert len(provider.calls) == 3
    assert len(sleep.delays) == 1
