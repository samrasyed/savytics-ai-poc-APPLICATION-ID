from __future__ import annotations

import pytest

from app.domain.schemas import AnalysisRecord, AnalysisResult
from app.intelligence.context import build_index
from app.intelligence.dates import check_date
from app.intelligence.text_match import SourceText, similar, tokens
from app.intelligence.validation import validate

DOC = (
    "Weekly sync. Priya will draft the pricing copy by Friday. "
    "Marco and Lena will fix the CSV export, it is a blocker. "
    "Testing depends on API readiness. The launch is planned for December 15. "
    "Budget of $12,000 is unconfirmed. We decided to drop the mobile app."
)
OTHER_DOC = "Kickoff notes. The launch is planned for December 20."


# Builds a result from raw fields with a summary filled in.
def result(**fields) -> AnalysisResult:
    return AnalysisResult.model_validate({"summary": "S.", **fields})


# Validates a result against DOC, optionally with one earlier document.
def run(res: AnalysisResult, previous: list[AnalysisRecord] | None = None) -> AnalysisResult:
    return validate(res, build_index("cur", "Weekly sync", DOC, previous or []))


# Builds a saved earlier analysis for cross-document checks.
def previous_record() -> AnalysisRecord:
    return AnalysisRecord(
        id="old",
        title="Kickoff",
        input_text=OTHER_DOC,
        result=result(),
        provider="mock",
        model="m",
        prompt_version="v",
        latency_ms=1,
        created_at="2026-01-01T00:00:00Z",
    )


# Checks tokens unify month names and drop ordinal suffixes.
def test_tokens_normalize_months_and_ordinals() -> None:
    assert tokens("December 15th, 2026") == tokens("Dec 15 2026") == ["dec", "15", "2026"]


# Checks task similarity catches rewordings but not different tasks.
def test_similar() -> None:
    assert similar("Fix the CSV export", "fix CSV export")
    assert similar("Draft the pricing copy", "Draft the pricing copy for the billing page")
    assert not similar("Draft the pricing copy", "Fix the CSV export")


# Checks evidence is rated verified, partial, not found or missing.
def test_evidence_status() -> None:
    source = SourceText(DOC)
    assert source.evidence_status("Priya will draft the pricing copy by Friday") == "verified"
    assert source.evidence_status("Priya will draft pricing copy by Friday") == "partial"
    assert source.evidence_status("Sam will order new laptops") == "not_found"
    assert source.evidence_status(None) == "missing"


# Checks dates are normalized, impossible dates flagged and relative dates left alone.
@pytest.mark.parametrize(
    ("text", "normalized", "invalid"),
    [
        ("December 15, 2026", "2026-12-15", False),
        ("15th of March 2027", "2027-03-15", False),
        ("2026-02-30", None, True),
        ("February 30", None, True),
        ("31/04/2026", None, True),
        ("25/12/2026", "2026-12-25", False),
        ("Friday", None, False),
        ("March 3", None, False),
    ],
)
def test_check_date(text: str, normalized: str | None, invalid: bool) -> None:
    check = check_date(text)
    assert check.normalized == normalized
    assert check.invalid is invalid


# Checks an ambiguous numeric date is reported but not normalized.
def test_ambiguous_numeric_date() -> None:
    check = check_date("03/04/2026")
    assert check.normalized is None and not check.invalid and "ambiguous" in check.reason


# Checks owners and deadlines missing from the source are removed and reported.
def test_unverified_owner_and_deadline_removed() -> None:
    out = run(
        result(
            action_items=[
                {
                    "task": "Draft the pricing copy",
                    "owners": ["Priya", "Sam"],
                    "due_date": "Monday",
                    "evidence": "Priya will draft the pricing copy by Friday",
                    "certainty": "high",
                }
            ]
        )
    )
    item = out.action_items[0]
    assert item.owners == ["Priya"] and item.owner == "Priya"
    assert item.due_date is None
    assert item.evidence_status == "verified" and item.basis == "fact"
    assert out.validation.checks["owners_removed"] == 1
    assert out.validation.checks["deadlines_removed"] == 1
    assert any("Sam" in i.message for i in out.validation.issues)


# Checks shared owners are kept and full dates are normalized.
def test_shared_owners_and_iso_deadline() -> None:
    out = run(
        result(
            action_items=[
                {"task": "Fix the CSV export", "owners": ["Marco", "Lena"], "due_date": "Dec 15"},
                {"task": "Prepare launch", "due_date": "December 15, 2026"},
            ]
        )
    )
    assert out.action_items[0].owner == "Marco, Lena"
    assert out.action_items[0].due_date == "Dec 15"
    assert out.action_items[1].due_date is None


# Checks near-duplicate tasks are merged and their owners combined.
def test_duplicate_tasks_merged() -> None:
    out = run(
        result(
            action_items=[
                {"task": "Fix the CSV export", "owners": ["Marco"]},
                {"task": "fix CSV export", "owners": ["Lena"], "due_date": "Friday"},
            ]
        )
    )
    assert len(out.action_items) == 1
    assert out.action_items[0].owners == ["Marco", "Lena"]
    assert out.action_items[0].due_date == "Friday"
    assert out.validation.checks["duplicates_merged"] == 1


# Checks tasks without evidence or with low certainty are labelled correctly.
def test_basis_labels() -> None:
    out = run(
        result(
            action_items=[
                {"task": "A", "evidence": "Testing depends on API readiness", "certainty": "low"},
                {"task": "B", "evidence": "Sam will order new laptops"},
            ]
        )
    )
    assert [a.basis for a in out.action_items] == ["inference", "assumption"]


# Checks entities not found in the document are removed and dates are normalized.
def test_entities_validated() -> None:
    out = run(
        result(
            entities={
                "people": ["Priya", "Bob"],
                "dates": [{"text": "December 15"}],
                "money": [{"text": "$12,000", "context": "budget"}],
            }
        )
    )
    assert [e.text for e in out.entities.people] == ["Priya"]
    assert out.entities.monetary_values[0].text == "$12,000"
    assert out.validation.checks["entities_removed"] == 1


# Checks gap questions are added for missing owners, deadlines and unresolved decisions.
def test_gap_questions_added() -> None:
    out = run(
        result(
            action_items=[{"task": "Book the design review"}],
            decisions=[
                {"description": "Delay push notifications", "status": "pending"},
                {"description": "Hire a QA contractor", "status": "proposed"},
            ],
            open_questions=[
                {
                    "question": "Who books the design review?",
                    "category": "missing_owner",
                    "related_to": "Book the design review",
                }
            ],
        )
    )
    categories = [q.category for q in out.open_question_details]
    assert categories.count("missing_owner") == 1
    assert "missing_deadline" in categories
    assert "unresolved_decision" in categories
    assert "missing_approval" in categories
    assert out.open_questions == [q.question for q in out.open_question_details]


# Checks re-validating a result does not duplicate generated gap questions.
def test_validation_is_idempotent_for_questions() -> None:
    once = run(result(action_items=[{"task": "Book the design review"}]))
    twice = run(once)
    assert len(twice.open_question_details) == len(once.open_question_details)


# Checks a decision maker missing from the document is removed and duplicates merged.
def test_decisions_validated() -> None:
    out = run(
        result(
            decisions=[
                {
                    "description": "Drop the mobile app",
                    "decision_maker": "The CEO",
                    "status": "approved",
                    "evidence": "We decided to drop the mobile app",
                },
                {"description": "drop the mobile app", "status": "confirmed"},
            ]
        )
    )
    assert len(out.decisions) == 1
    decision = out.decisions[0]
    assert decision.status == "confirmed"
    assert decision.decision_maker is None
    assert decision.basis == "fact"


# Checks a cross-document contradiction is kept and verified against each source.
def test_cross_document_contradiction_kept() -> None:
    res = result(
        contradictions=[
            {
                "description": "Launch date differs",
                "conflict_type": "date",
                "values": [
                    {
                        "value": "December 15",
                        "document_id": "cur",
                        "is_current": True,
                        "evidence": "The launch is planned for December 15",
                    },
                    {
                        "value": "December 20",
                        "document_id": "old",
                        "is_current": False,
                        "evidence": "The launch is planned for December 20",
                    },
                ],
            }
        ]
    )
    out = run(res, [previous_record()])
    conflict = out.contradictions[0]
    assert conflict.scope == "cross_document"
    assert [v.evidence_status for v in conflict.values] == ["verified", "verified"]
    assert conflict.resolution_status == "unresolved"


# Checks contradictions with identical values or without the current document are dropped.
def test_non_contradictions_dropped() -> None:
    same = {
        "description": "Same date",
        "values": [
            {"value": "Dec 15", "document_id": "cur"},
            {"value": "December 15", "document_id": "cur"},
        ],
    }
    elsewhere = {
        "description": "Only old docs",
        "values": [
            {"value": "A", "document_id": "old", "is_current": False},
            {"value": "B", "document_id": "old", "is_current": False},
        ],
    }
    out = run(result(contradictions=[same, elsewhere]), [previous_record()])
    assert out.contradictions == []
    assert out.validation.checks["items_dropped"] == 2


# Checks unsupported dependencies are dropped and supported ones kept.
def test_dependencies_need_evidence() -> None:
    out = run(
        result(
            dependencies=[
                {
                    "source_task": "API readiness",
                    "dependent_task": "Testing",
                    "evidence": "Testing depends on API readiness",
                },
                {"source_task": "Design", "dependent_task": "Deployment", "evidence": None},
            ]
        )
    )
    assert [d.dependent_task for d in out.dependencies] == ["Testing"]


# Checks inferred risks keep inferred severity and get the right basis.
def test_risk_severity_and_basis() -> None:
    out = run(
        result(
            risks=[
                {
                    "description": "CSV export blocker",
                    "severity": "high",
                    "severity_source": "explicit",
                    "origin": "inferred",
                    "evidence": "it is a blocker",
                    "document_id": "cur",
                },
                {
                    "description": "Budget unconfirmed",
                    "origin": "explicit",
                    "evidence": "Budget of $12,000 is unconfirmed",
                },
            ]
        )
    )
    assert out.risks[0].severity_source == "inferred"
    assert out.risks[0].basis == "inference"
    assert out.risks[1].basis == "fact"


# Checks a contradiction is dropped when its values have no quote in their documents.
def test_contradiction_without_supported_values_dropped() -> None:
    res = result(
        contradictions=[
            {
                "description": "Owner differs",
                "conflict_type": "owner",
                "values": [
                    {"value": "unassigned", "document_id": "cur", "evidence": "nobody owns it"},
                    {
                        "value": "Marco",
                        "document_id": "cur",
                        "evidence": "Marco and Lena will fix the CSV export",
                    },
                ],
            }
        ]
    )
    out = run(res)
    assert out.contradictions == []
    assert out.validation.checks["evidence_unverified"] == 1
    assert "backed by a quote" in out.validation.issues[-1].message
