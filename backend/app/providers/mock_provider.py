from __future__ import annotations

import copy
import json
import re
import time
from collections.abc import Callable
from typing import Any

from app.domain.errors import (
    ContextLengthError,
    ProviderAuthError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitError,
)
from app.prompts.analysis_prompt import REPAIR_MARKER
from app.prompts.intelligence_prompt import INTELLIGENCE_MARKER
from app.providers.base import LLMMessage, ProviderResponse
from app.providers.mock_samples import select_sample

MOCK_MODEL = "mock-analyzer-v1"

_TITLE_RE = re.compile(r"^Title(?: of D0)?: (.*)$", re.MULTILINE)
_DOC_RE = re.compile(r"<document>\n(.*?)\n</document>", re.DOTALL)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_DEPENDS_RE = re.compile(
    r"^(?P<dependent>.+?)\s+(?:depends on|is blocked by|requires|waits for)\s+(?P<source>.+?)[.!?]?$",
    re.IGNORECASE,
)
_ONCE_RE = re.compile(
    r"^(?:once|after)\s+(?P<source>.+?),\s*(?P<dependent>.+?)[.!?]?$", re.IGNORECASE
)
_RISK_WORDS = ("blocker", "risk", "delay", "unconfirmed", "behind", "over budget", "concern")


# Splits text into sentences, skipping mock trigger tokens.
def _sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENTENCE_RE.split(text)]
    return [p for p in parts if p and "[[mock:" not in p]


# Replaces "@N" placeholders with real sentences from the document so evidence can be verified.
def _fill_evidence(value: Any, sentences: list[str]) -> Any:
    if isinstance(value, dict):
        return {k: _fill_evidence(v, sentences) for k, v in value.items()}
    if isinstance(value, list):
        return [_fill_evidence(v, sentences) for v in value]
    if isinstance(value, str) and re.fullmatch(r"@\d+", value):
        return sentences[int(value[1:]) % len(sentences)] if sentences else None
    return value


# Finds dependencies stated in sentences like "X depends on Y" or "Once X, Y".
def _mock_dependencies(sentences: list[str]) -> list[dict[str, Any]]:
    out = []
    for sentence in sentences:
        match = _DEPENDS_RE.match(sentence) or _ONCE_RE.match(sentence)
        if match:
            out.append(
                {
                    "source_task": match["source"],
                    "dependent_task": match["dependent"],
                    "description": f"{match['dependent']} waits for {match['source']}.",
                    "evidence": sentence,
                }
            )
    return out


# Finds sentences that mention blockers, delays or unconfirmed items and reports them as risks.
def _mock_risks(sentences: list[str]) -> list[dict[str, Any]]:
    out = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(word in lowered for word in _RISK_WORDS):
            explicit = "blocker" in lowered or "risk" in lowered
            out.append(
                {
                    "description": sentence.rstrip(".!?"),
                    "category": "technical" if "blocker" in lowered else "delay",
                    "severity": "high" if explicit else "medium",
                    "severity_source": "inferred",
                    "origin": "explicit" if explicit else "inferred",
                    "reason": "The document describes an unresolved problem that could slip the plan.",
                    "evidence": sentence,
                    "source": "D0",
                    "resolution_status": "unresolved",
                    "mitigation": "Assign an owner and agree a date to resolve it.",
                }
            )
    return out[:5]


class MockProvider:
    name = "mock"

    # Sets up the mock with a simulated latency and an injectable sleep function.
    def __init__(self, latency_ms: int = 300, sleep: Callable[[float], None] = time.sleep) -> None:
        self.model = MOCK_MODEL
        self._latency_s = max(latency_ms, 0) / 1000
        self._sleep = sleep

    # Returns the content of the first message with the given role.
    @staticmethod
    def _first(messages: list[LLMMessage], role: str) -> str:
        for m in messages:
            if m["role"] == role:
                return m["content"]
        return ""

    # Tells whether this call is a repair request after a bad reply.
    @staticmethod
    def _is_repair(messages: list[LLMMessage]) -> bool:
        return any(m["role"] == "user" and REPAIR_MARKER in m["content"] for m in messages)

    # Wraps text in a successful ProviderResponse.
    def _respond(self, content: str) -> ProviderResponse:
        return ProviderResponse(
            content=content,
            model=self.model,
            finish_reason="stop",
            prompt_tokens=None,
            completion_tokens=None,
        )

    # Picks a canned sample that fits the text, fills in the title and real evidence quotes.
    @staticmethod
    def _build_result(title: str, text: str) -> dict[str, Any]:
        sample = copy.deepcopy(select_sample(text))
        sample["summary"] = sample["summary"].replace("{title}", title or "Untitled")
        return _fill_evidence(sample, _sentences(text))

    # Builds the intelligence reply from risk and dependency sentences found in the text.
    def _intelligence(self, text: str, messages: list[LLMMessage]) -> ProviderResponse:
        if "[[mock:intel_ratelimit]]" in text:
            raise RateLimitError(retry_after_seconds=2)
        if "[[mock:intel_malformed]]" in text:
            return self._respond("The checks could not be completed.")
        sentences = _sentences(text)
        contradictions = []
        if "[[mock:conflict]]" in text and len(sentences) >= 2:
            contradictions.append(
                {
                    "description": "Two statements give different values for the same item.",
                    "conflict_type": "date",
                    "values": [
                        {"value": sentences[0], "source": "D0", "evidence": sentences[0]},
                        {"value": sentences[1], "source": "D0", "evidence": sentences[1]},
                    ],
                    "resolution_status": "unresolved",
                    "suggested_action": "Confirm the correct value with the owner.",
                }
            )
        payload = {
            "contradictions": contradictions,
            "risks": _mock_risks(sentences),
            "dependencies": _mock_dependencies(sentences),
        }
        return self._respond(json.dumps(payload))

    # Returns a canned analysis, or simulates an error when the text has a [[mock:...]] trigger.
    def complete(self, messages: list[LLMMessage], *, json_mode: bool) -> ProviderResponse:
        if self._latency_s:
            self._sleep(self._latency_s)

        user = self._first(messages, "user")
        title_match = _TITLE_RE.search(user)
        doc_match = _DOC_RE.search(user)
        title = title_match.group(1).strip() if title_match else ""
        text = doc_match.group(1) if doc_match else user

        if "[[mock:ratelimit]]" in text:
            raise RateLimitError(retry_after_seconds=2)
        if "[[mock:timeout]]" in text:
            raise ProviderTimeoutError()
        if "[[mock:unavailable]]" in text:
            raise ProviderUnavailableError()
        if "[[mock:auth]]" in text:
            raise ProviderAuthError()
        if "[[mock:context]]" in text:
            raise ContextLengthError()

        if INTELLIGENCE_MARKER in self._first(messages, "system"):
            return self._intelligence(text, messages)

        result = self._build_result(title, text)

        if "[[mock:malformed]]" in text:
            return self._respond("I'm sorry, I can't produce a structured summary for this one.")
        if "[[mock:malformed_once]]" in text and not self._is_repair(messages):
            return self._respond("Here is my analysis: the meeting went well and people agreed.")
        if "[[mock:invalid_schema]]" in text:
            result.pop("summary", None)
            return self._respond(json.dumps(result))
        if "[[mock:fenced]]" in text:
            return self._respond("```json\n" + json.dumps(result, indent=2) + "\n```")

        return self._respond(json.dumps(result))
