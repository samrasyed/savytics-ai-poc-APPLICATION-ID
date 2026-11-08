from __future__ import annotations

import logging
import random
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypeVar

from pydantic import ValidationError

from app.config import Settings
from app.db.repository import AnalysisRepository
from app.domain.errors import (
    TRANSIENT_ERRORS,
    AnalysisNotFoundError,
    AppError,
    EmptyInputError,
    InputTooLongError,
    MalformedResponseError,
    RateLimitError,
)
from app.domain.schemas import (
    AnalysisListResponse,
    AnalysisRecord,
    AnalysisResult,
    AnalyzeRequest,
    IntelligenceStatus,
)
from app.intelligence.context import DocumentIndex, build_index
from app.intelligence.validation import validate
from app.logging_config import request_id_var
from app.prompts.analysis_prompt import (
    PROMPT_VERSION,
    build_repair_prompt,
    build_system_prompt,
    build_user_prompt,
)
from app.prompts.intelligence_prompt import (
    MODULES,
    build_intelligence_system_prompt,
    build_intelligence_user_prompt,
)
from app.providers.base import LLMMessage, LLMProvider, ProviderResponse
from app.services.json_extraction import JSONExtractionError, extract_json

logger = logging.getLogger(__name__)

REPAIR_ECHO_CHARS = 4000
RAW_LOG_CHARS = 2000
_BLANK_RUN_RE = re.compile(r"\n(?:[ \t]*\n){3,}")

T = TypeVar("T")


@dataclass
class _CallStats:
    attempts: int = 0
    repair_used: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0


# Unifies line endings, trims the text and collapses long runs of blank lines.
def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return _BLANK_RUN_RE.sub("\n\n\n", text)


# Summarizes a parse or validation error in at most 5 short lines, without input values.
def summarize_error(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        lines = []
        for err in exc.errors(include_input=False, include_url=False)[:5]:
            path = ".".join(str(p) for p in err.get("loc", ())) or "root"
            lines.append(f"{path}: {err.get('msg', 'invalid value')}")
        return "\n".join(lines) or "root: invalid object"
    return f"root: {exc}"[:300]


# Tells whether the value is a valid UUID string.
def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        return False
    return True


# Parses an extraction reply into an analysis result.
def _parse_extraction(content: str) -> AnalysisResult:
    return AnalysisResult.model_validate(extract_json(content))


# Removes results of earlier intelligence and validation runs so they can be recomputed.
def _strip_derived(result: AnalysisResult) -> AnalysisResult:
    questions = [q for q in result.open_question_details if q.origin != "check"]
    return result.model_copy(
        update={
            "contradictions": [],
            "risks": [],
            "dependencies": [],
            "open_question_details": questions,
            "open_questions": [q.question for q in questions],
        }
    )


class AnalysisService:
    # Wires in the provider, repository, settings and injectable time helpers.
    def __init__(
        self,
        provider: LLMProvider,
        repository: AnalysisRepository,
        settings: Settings,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.perf_counter,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        jitter: Callable[[], float] = lambda: random.uniform(0.0, 0.25),
    ) -> None:
        self.provider = provider
        self.repository = repository
        self.settings = settings
        self._sleep = sleep
        self._clock = clock
        self._now = now
        self._jitter = jitter

    # Validates the input, runs extraction, intelligence and validation, then saves the record.
    def analyze(self, request: AnalyzeRequest) -> AnalysisRecord:
        title = request.title.strip()
        text = normalize_text(request.text)

        if not title or not text:
            raise EmptyInputError()
        if len(title) > self.settings.MAX_TITLE_CHARS:
            raise InputTooLongError(
                field="title", length=len(title), limit=self.settings.MAX_TITLE_CHARS
            )
        if len(text) > self.settings.MAX_INPUT_CHARS:
            raise InputTooLongError(
                field="text", length=len(text), limit=self.settings.MAX_INPUT_CHARS
            )

        messages: list[LLMMessage] = [
            {"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": build_user_prompt(title, text)},
        ]

        record_id = str(uuid.uuid4())
        stats = _CallStats()
        started = self._clock()
        extraction, response = self._call_and_parse(messages, stats, started, _parse_extraction)
        result = self._enrich(record_id, title, text, extraction, stats, started, strict=False)
        latency_ms = int(round((self._clock() - started) * 1000))

        record = AnalysisRecord(
            id=record_id,
            title=title,
            input_text=text,
            result=result,
            provider=self.provider.name,
            model=response.model or self.provider.model,
            prompt_version=PROMPT_VERSION,
            latency_ms=latency_ms,
            created_at=self._now(),
        )
        self.repository.save(record)

        logger.info(
            "analysis complete provider=%s model=%s attempts=%d repair_used=%s latency_ms=%d "
            "prompt_tokens=%s completion_tokens=%s input_chars=%d intelligence=%s",
            self.provider.name,
            record.model,
            stats.attempts,
            stats.repair_used,
            latency_ms,
            stats.prompt_tokens or "-",
            stats.completion_tokens or "-",
            len(text),
            result.intelligence.status,
        )
        return record

    # Re-runs intelligence and validation on a saved analysis against the latest documents.
    def rerun_intelligence(self, analysis_id: str) -> AnalysisRecord:
        record = self.get(analysis_id)
        stats = _CallStats()
        started = self._clock()
        result = self._enrich(
            record.id,
            record.title,
            record.input_text,
            _strip_derived(record.result),
            stats,
            started,
            strict=True,
        )
        updated = record.model_copy(update={"result": result})
        self.repository.update_result(record.id, result)
        logger.info(
            "intelligence rerun id=%s attempts=%d status=%s",
            record.id,
            stats.attempts,
            result.intelligence.status,
        )
        return updated

    # Returns one saved analysis, or raises NOT_FOUND.
    def get(self, analysis_id: str) -> AnalysisRecord:
        if not _is_uuid(analysis_id):
            raise AnalysisNotFoundError()
        record = self.repository.get(analysis_id)
        if record is None:
            raise AnalysisNotFoundError()
        return record

    # Returns a page of saved analyses with the total count.
    def list(self, limit: int, offset: int) -> AnalysisListResponse:
        items, total = self.repository.list(limit, offset)
        return AnalysisListResponse(items=items, total=total, limit=limit, offset=offset)

    # Deletes one saved analysis, or raises NOT_FOUND.
    def delete(self, analysis_id: str) -> None:
        if not _is_uuid(analysis_id) or not self.repository.delete(analysis_id):
            raise AnalysisNotFoundError()

    # Adds contradictions, risks and dependencies to an extraction and validates everything.
    def _enrich(
        self,
        record_id: str,
        title: str,
        text: str,
        extraction: AnalysisResult,
        stats: _CallStats,
        started: float,
        *,
        strict: bool,
    ) -> AnalysisResult:
        if not self.settings.LLM_ENABLE_INTELLIGENCE:
            index = build_index(record_id, title, text, [])
            status = IntelligenceStatus(
                status="disabled", modules={m.KEY: "not_run" for m in MODULES}
            )
            return validate(extraction.model_copy(update={"intelligence": status}), index)

        previous = self.repository.recent(self.settings.CROSS_DOC_CONTEXT_LIMIT, record_id)
        index = build_index(record_id, title, text, previous)
        sections, status = self._run_intelligence(index, extraction, stats, started, strict)
        enriched = extraction.model_copy(update={**sections, "intelligence": status})
        return validate(enriched, index)

    # Calls the model for the intelligence modules and parses each module's section independently.
    def _run_intelligence(
        self,
        index: DocumentIndex,
        extraction: AnalysisResult,
        stats: _CallStats,
        started: float,
        strict: bool,
    ) -> tuple[dict[str, Any], IntelligenceStatus]:
        messages: list[LLMMessage] = [
            {"role": "system", "content": build_intelligence_system_prompt()},
            {"role": "user", "content": build_intelligence_user_prompt(index, extraction)},
        ]
        compared = len(index.previous)
        try:
            raw, _ = self._call_and_parse(messages, stats, started, extract_json)
        except AppError as exc:
            if strict:
                raise
            logger.warning("intelligence pass failed code=%s; saving extraction only", exc.code)
            return {}, IntelligenceStatus(
                status="failed",
                modules={m.KEY: "failed" for m in MODULES},
                message=exc.message,
                documents_compared=compared,
            )

        sections: dict[str, Any] = {}
        modules: dict[str, Any] = {}
        for module in MODULES:
            try:
                sections[module.KEY] = module.parse(raw.get(module.KEY), index)
                modules[module.KEY] = "ok"
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "intelligence module failed module=%s error=%s", module.KEY, type(exc).__name__
                )
                sections[module.KEY] = []
                modules[module.KEY] = "failed"
        ok = sum(1 for state in modules.values() if state == "ok")
        overall = "complete" if ok == len(MODULES) else "failed" if ok == 0 else "partial"
        message = None if overall == "complete" else "Some checks could not be completed."
        return sections, IntelligenceStatus(
            status=overall, modules=modules, message=message, documents_compared=compared
        )

    # Calls the provider, retrying transient errors with backoff within the time budget.
    def _call_with_retries(
        self, messages: list[LLMMessage], stats: _CallStats, started: float
    ) -> ProviderResponse:
        max_retries = self.settings.LLM_MAX_TRANSIENT_RETRIES
        budget = self.settings.LLM_TOTAL_BUDGET_SECONDS
        retry = 0
        while True:
            stats.attempts += 1
            try:
                response = self.provider.complete(messages, json_mode=self.settings.LLM_JSON_MODE)
            except TRANSIENT_ERRORS as exc:
                if retry >= max_retries:
                    raise
                if isinstance(exc, RateLimitError) and exc.retry_after_seconds is not None:
                    if exc.retry_after_seconds > self.settings.LLM_MAX_RETRY_AFTER_SECONDS:
                        raise
                    delay = exc.retry_after_seconds
                else:
                    delay = float(2**retry) + self._jitter()
                elapsed = self._clock() - started
                if elapsed + delay >= budget:
                    logger.warning("retry skipped: would exceed time budget code=%s", exc.code)
                    raise
                retry += 1
                logger.warning(
                    "transient provider error code=%s retry=%d/%d delay_s=%.2f",
                    exc.code,
                    retry,
                    max_retries,
                    delay,
                )
                self._sleep(delay)
                continue
            if response.prompt_tokens:
                stats.prompt_tokens += response.prompt_tokens
            if response.completion_tokens:
                stats.completion_tokens += response.completion_tokens
            return response

    # Calls the model and parses its reply, asking it to fix the reply once if it is invalid.
    def _call_and_parse(
        self,
        messages: list[LLMMessage],
        stats: _CallStats,
        started: float,
        parse: Callable[[str], T],
    ) -> tuple[T, ProviderResponse]:
        response = self._call_with_retries(messages, stats, started)
        repairs_left = self.settings.LLM_MAX_REPAIR_ATTEMPTS
        while True:
            try:
                return parse(response.content), response
            except (JSONExtractionError, ValidationError) as exc:
                error_summary = summarize_error(exc)
                if repairs_left <= 0:
                    logger.warning(
                        "malformed AI output after repair attempts request_id=%s "
                        "truncated=%s errors=%s raw=%r",
                        request_id_var.get(),
                        response.truncated,
                        error_summary.replace("\n", "; "),
                        response.content[:RAW_LOG_CHARS],
                    )
                    raise MalformedResponseError() from None
                repairs_left -= 1
                stats.repair_used = True
                logger.warning(
                    "AI output failed validation; attempting repair errors=%s",
                    error_summary.replace("\n", "; "),
                )
                repair_messages: list[LLMMessage] = [
                    *messages,
                    {"role": "assistant", "content": response.content[:REPAIR_ECHO_CHARS]},
                    {"role": "user", "content": build_repair_prompt(error_summary)},
                ]
                response = self._call_with_retries(repair_messages, stats, started)
