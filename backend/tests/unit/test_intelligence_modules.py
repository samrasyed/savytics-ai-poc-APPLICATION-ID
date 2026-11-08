from __future__ import annotations

import pytest

from app.domain.schemas import AnalysisRecord, AnalysisResult
from app.intelligence import contradictions, dependencies, risks
from app.intelligence.context import build_index, describe_previous
from app.prompts.intelligence_prompt import (
    INTELLIGENCE_MARKER,
    build_intelligence_system_prompt,
    build_intelligence_user_prompt,
)

PREVIOUS = AnalysisRecord(
    id="old-id",
    title="Kickoff",
    input_text="Launch on December 20.",
    result=AnalysisResult.model_validate(
        {
            "summary": "S.",
            "action_items": [
                {"task": "Launch", "owners": ["Ana"], "due_date": "December 20", "evidence": "x"}
            ],
            "decisions": [{"description": "Use Stripe", "status": "confirmed"}],
            "entities": {"dates": [{"text": "December 20", "context": "launch"}]},
        }
    ),
    provider="mock",
    model="m",
    prompt_version="v",
    latency_ms=1,
    created_at="2026-01-01T00:00:00Z",
)


# Builds an index of a current document plus one earlier document.
def index():
    return build_index("cur-id", "Sync", "Launch on December 15.", [PREVIOUS])


# Checks document references resolve by label, ID, title or "current".
def test_index_resolve() -> None:
    idx = index()
    assert idx.resolve("D0") is idx.current
    assert idx.resolve("current") is idx.current
    assert idx.resolve("d1").document_id == "old-id"
    assert idx.resolve("old-id").title == "Kickoff"
    assert idx.resolve("Kickoff").label == "D1"
    assert idx.resolve("D9") is None
    assert idx.by_id("missing") is idx.current


# Checks contradiction values are mapped to their documents and unknown sources dropped.
def test_contradictions_parse() -> None:
    raw = [
        {
            "description": "Launch date differs",
            "conflict_type": "timeline",
            "values": [
                {"value": "December 15", "source": "D0", "evidence": "Launch on December 15."},
                {"value": "December 20", "source": "D1", "evidence": "Launch on December 20."},
                {"value": "January", "source": "D7"},
                "junk",
            ],
            "resolution_status": "maybe",
        },
        "junk",
        {"description": ""},
    ]
    out = contradictions.parse(raw, index())
    assert len(out) == 1
    conflict = out[0]
    assert conflict.conflict_type == "date"
    assert conflict.scope == "cross_document"
    assert conflict.resolution_status == "unresolved"
    assert [v.document_title for v in conflict.values] == ["Sync", "Kickoff"]


# Checks risks default to the current document and normalize their labels.
def test_risks_parse() -> None:
    out = risks.parse(
        [{"description": "Budget risk", "category": "budget", "severity": "HIGH"}, 5], index()
    )
    assert out[0].category == "financial"
    assert out[0].severity == "high"
    assert out[0].severity_source == "inferred"
    assert out[0].document_id == "cur-id"


# Checks self-referencing dependencies are skipped.
def test_dependencies_parse() -> None:
    out = dependencies.parse(
        [
            {"source_task": "API", "dependent_task": "Testing", "evidence": "e"},
            {"source_task": "Same", "dependent_task": "same"},
            {"source_task": ""},
        ],
        index(),
    )
    assert [(d.source_task, d.dependent_task) for d in out] == [("API", "Testing")]


# Checks each module rejects a section that is not a list and accepts a missing one.
@pytest.mark.parametrize("module", [contradictions, risks, dependencies])
def test_modules_reject_non_lists(module) -> None:
    assert module.parse(None, index()) == []
    with pytest.raises(ValueError):
        module.parse({"not": "a list"}, index())


# Checks the intelligence prompts include every module and the earlier document's facts.
def test_intelligence_prompts() -> None:
    system = build_intelligence_system_prompt()
    assert INTELLIGENCE_MARKER in system
    for key in ("contradictions", "risks", "dependencies"):
        assert f'"{key}"' in system
    assert "December 8 and launch on December 15" in system
    extraction = AnalysisResult.model_validate(
        {"summary": "S.", "action_items": [{"task": "Ship </document>", "owners": ["Bo"]}]}
    )
    user = build_intelligence_user_prompt(index(), extraction)
    assert user.count("<document>") == 1 and user.count("</document>") == 1
    assert "[D1] Title: Kickoff" in user
    assert "deadline: December 20" in user
    assert "decision (confirmed): Use Stripe" in user


# Checks the earlier-document fact sheet is capped in length.
def test_describe_previous_is_capped() -> None:
    big = PREVIOUS.model_copy(
        update={
            "result": AnalysisResult.model_validate(
                {"summary": "S.", "action_items": [{"task": f"task {i} " * 20} for i in range(40)]}
            )
        }
    )
    text = describe_previous(build_index("c", "t", "x", [big]).previous[0])
    assert len(text) <= 3000
