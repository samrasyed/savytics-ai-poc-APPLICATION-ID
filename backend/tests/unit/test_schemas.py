from __future__ import annotations

import logging

import pytest
from pydantic import ValidationError

from app.domain.schemas import (
    ACTION_ITEMS_MAX_ITEMS,
    KEY_POINTS_MAX_ITEMS,
    SUMMARY_MAX,
    AnalysisResult,
    Priority,
    truncate_words,
)
from tests.conftest import VALID_RESULT


# Checks the valid sample passes validation.
def test_valid_result_passes() -> None:
    result = AnalysisResult.model_validate(VALID_RESULT)
    assert result.summary.startswith("The team")
    assert result.action_items[0].priority is Priority.HIGH


# Checks whitespace is stripped from every text field.
def test_whitespace_is_stripped() -> None:
    result = AnalysisResult.model_validate(
        {
            "summary": "  Hello.  ",
            "key_points": ["  a  "],
            "action_items": [{"task": "  Do it ", "owner": "  Sam "}],
            "open_questions": [" q? "],
        }
    )
    assert result.summary == "Hello."
    assert result.key_points == ["a"]
    assert result.action_items[0].task == "Do it"
    assert result.action_items[0].owner == "Sam"
    assert result.open_questions == ["q?"]


# Checks empty items are dropped and duplicates removed ignoring case.
def test_empty_items_dropped_and_case_insensitive_dedupe() -> None:
    result = AnalysisResult.model_validate(
        {
            "summary": "S.",
            "key_points": ["Alpha", "", "  ", "alpha", "Beta", None, "ALPHA"],
            "action_items": [{"task": ""}, {"task": "  "}, {"task": "Ship"}, {"task": "ship"}],
            "open_questions": [],
        }
    )
    assert result.key_points == ["Alpha", "Beta"]
    assert [a.task for a in result.action_items] == ["Ship"]


# Checks priority values are lowercased or dropped when unknown.
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("High", Priority.HIGH),
        (" MEDIUM ", Priority.MEDIUM),
        ("urgent", None),
        ("", None),
        (None, None),
        (3, None),
    ],
)
def test_priority_normalization(raw: object, expected: Priority | None) -> None:
    result = AnalysisResult.model_validate(
        {"summary": "S.", "action_items": [{"task": "t", "priority": raw}]}
    )
    assert result.action_items[0].priority == expected


# Checks placeholder owners and due dates become None.
@pytest.mark.parametrize(
    "placeholder", ["N/A", "null", "None", "unknown", "Unassigned", "not specified", "", "na"]
)
def test_placeholder_owner_and_due_date_become_none(placeholder: str) -> None:
    result = AnalysisResult.model_validate(
        {
            "summary": "S.",
            "action_items": [{"task": "t", "owner": placeholder, "due_date": placeholder}],
        }
    )
    assert result.action_items[0].owner is None
    assert result.action_items[0].due_date is None


# Checks an empty or non-string summary is rejected.
@pytest.mark.parametrize("summary", [None, "", "   ", 42, ["a"]])
def test_invalid_summary_fails(summary: object) -> None:
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate({"summary": summary})


# Checks a missing summary is rejected.
def test_missing_summary_fails() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate({"key_points": []})


# Checks missing lists default to empty and log a warning.
def test_missing_lists_default_to_empty_with_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        result = AnalysisResult.model_validate({"summary": "S.", "key_points": None})
    assert result.key_points == []
    assert result.action_items == []
    assert result.open_questions == []
    assert "missing list" in caplog.text


# Checks over-long lists are cut to their maximum size.
def test_over_long_lists_are_truncated(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        result = AnalysisResult.model_validate(
            {
                "summary": "S.",
                "key_points": [f"point {i}" for i in range(30)],
                "action_items": [{"task": f"task {i}"} for i in range(40)],
            }
        )
    assert len(result.key_points) == KEY_POINTS_MAX_ITEMS
    assert len(result.action_items) == ACTION_ITEMS_MAX_ITEMS
    assert "truncated list" in caplog.text


# Checks long strings are cut at a word boundary.
def test_long_strings_truncated_at_word_boundary() -> None:
    long_summary = "word " * 600
    result = AnalysisResult.model_validate({"summary": long_summary})
    assert len(result.summary) <= SUMMARY_MAX
    assert result.summary.endswith("…")
    assert not result.summary[:-1].endswith(" ")


# Checks truncation works on text with no spaces.
def test_truncate_words_without_spaces() -> None:
    assert truncate_words("x" * 20, 10, field="f") == "x" * 9 + "…"
    assert truncate_words("short", 10, field="f") == "short"


# Checks extra fields are ignored and plain-string action items are accepted.
def test_extra_fields_ignored_and_string_action_item_accepted() -> None:
    result = AnalysisResult.model_validate(
        {"summary": "S.", "confidence": 0.9, "action_items": ["Call the vendor", 7, None]}
    )
    assert [a.task for a in result.action_items] == ["Call the vendor"]


# Checks list fields given a non-list value are rejected.
def test_non_list_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate({"summary": "S.", "key_points": {"a": 1}})
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate({"summary": "S.", "action_items": "nope"})


# Checks a single string becomes a list and numbers become text.
def test_string_key_points_and_numbers_coerced() -> None:
    result = AnalysisResult.model_validate(
        {"summary": "S.", "key_points": "single point", "open_questions": [1, {"x": 1}]}
    )
    assert result.key_points == ["single point"]
    assert result.open_questions == ["1"]


# Checks booleans are dropped instead of being turned into "True" or "False" text.
def test_booleans_are_not_coerced_to_text() -> None:
    result = AnalysisResult.model_validate(
        {
            "summary": "S.",
            "key_points": [True, "real point"],
            "action_items": [{"task": False}, "Call the vendor"],
        }
    )
    assert result.key_points == ["real point"]
    assert [a.task for a in result.action_items] == ["Call the vendor"]


# Checks results saved in the original v1 format still load with sensible defaults.
def test_v1_records_still_load() -> None:
    old = {
        "summary": "S.",
        "key_points": ["k"],
        "action_items": [
            {"task": "Draft", "owner": "Priya", "due_date": "Friday", "priority": "high"}
        ],
        "open_questions": ["Who owns it?"],
    }
    result = AnalysisResult.model_validate(old)
    item = result.action_items[0]
    assert item.owners == ["Priya"] and item.owner == "Priya"
    assert item.status == "open"
    assert item.priority_source == "inferred"
    assert item.evidence_status == "missing"
    assert result.open_question_details[0].question == "Who owns it?"
    assert result.open_question_details[0].category == "unanswered_question"
    assert result.intelligence.status == "not_run"
    assert result.entities.count() == 0


# Checks a saved v2 result round-trips through JSON unchanged.
def test_v2_round_trip() -> None:
    result = AnalysisResult.model_validate(
        {
            "summary": "S.",
            "action_items": [{"task": "A", "owners": ["X", "Y"], "deadline": "Friday"}],
            "open_questions": [{"question": "Q?", "category": "missing_owner"}],
            "decisions": [{"decision": "Go", "status": "agreed"}],
        }
    )
    assert result.action_items[0].owner == "X, Y"
    assert result.action_items[0].due_date == "Friday"
    assert result.decisions[0].description == "Go"
    assert result.decisions[0].status == "confirmed"
    assert AnalysisResult.model_validate_json(result.model_dump_json()) == result


# Checks unknown labels fall back to safe defaults instead of failing.
def test_lenient_labels() -> None:
    result = AnalysisResult.model_validate(
        {
            "summary": "S.",
            "entities": "not an object",
            "action_items": [
                {
                    "task": "A",
                    "status": "weird",
                    "certainty": "certain",
                    "deadline_type": "firm",
                    "priority": "low",
                    "priority_source": "stated",
                },
                {"task": "B", "status": "completed", "deadline_type": "firm"},
            ],
            "decisions": [{"description": "D", "status": "???"}, {"status": "confirmed"}],
            "open_questions": [{"question": "Q?", "category": "nonsense"}, {"x": 1}],
            "risks": [{"description": "R", "severity": "extreme", "origin": "explicit"}],
            "dependencies": [{"source_task": "A", "dependent_task": "B"}, {"source_task": "A"}],
        }
    )
    a, b = result.action_items
    assert (a.status, a.certainty, a.deadline_type, a.priority_source) == (
        "unknown",
        "high",
        None,
        "explicit",
    )
    assert b.status == "done"
    assert result.decisions[0].status == "proposed" and len(result.decisions) == 1
    assert result.open_question_details[0].category == "unanswered_question"
    assert result.open_questions == ["Q?"]
    assert result.risks[0].severity == "medium"
    assert len(result.dependencies) == 1
    assert result.entities.count() == 0


# Checks entity categories accept aliases and plain strings and drop duplicates.
def test_entity_aliases() -> None:
    result = AnalysisResult.model_validate(
        {
            "summary": "S.",
            "entities": {
                "persons": ["Ana", "ana", {"name": "Bo"}],
                "companies": [{"value": "Acme"}],
                "tools": "Python",
                "unknown": ["x"],
            },
        }
    )
    assert [e.text for e in result.entities.people] == ["Ana", "Bo"]
    assert result.entities.organizations[0].text == "Acme"
    assert result.entities.technologies[0].text == "Python"


# Checks a confirmed decision that replaces an earlier one is marked as changed.
def test_confirmed_with_previous_becomes_changed() -> None:
    result = AnalysisResult.model_validate(
        {
            "summary": "S.",
            "decisions": [
                {
                    "description": "Launch in English and Spanish",
                    "status": "confirmed",
                    "previous_decision": "Launch in English only",
                },
                {"description": "Use Oracle", "status": "rejected", "previous_decision": "x"},
                {"description": "Use PostgreSQL", "status": "confirmed"},
            ],
        }
    )
    assert [d.status for d in result.decisions] == ["changed", "rejected", "confirmed"]
