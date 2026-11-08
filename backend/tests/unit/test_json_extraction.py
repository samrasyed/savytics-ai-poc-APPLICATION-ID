from __future__ import annotations

import pytest

from app.services.json_extraction import JSONExtractionError, extract_json


# Checks plain JSON is parsed as is.
def test_plain_json() -> None:
    assert extract_json('{"a": 1}') == {"a": 1}


# Checks a leading BOM and surrounding whitespace are ignored.
def test_bom_and_whitespace() -> None:
    assert extract_json('﻿  \n{"a": 1}\n ') == {"a": 1}


# Checks JSON inside a ```json code fence is extracted.
def test_fenced_with_json_label() -> None:
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


# Checks JSON inside an unlabeled code fence is extracted.
def test_fenced_without_label() -> None:
    assert extract_json('```\n{"a": 1}\n```') == {"a": 1}


# Checks prose before the JSON object is skipped.
def test_leading_prose() -> None:
    assert extract_json('Here is the result: {"a": {"b": 2}}') == {"a": {"b": 2}}


# Checks prose after the JSON object is ignored.
def test_trailing_prose() -> None:
    assert extract_json('{"a": 1}\nHope this helps!') == {"a": 1}


# Checks braces inside strings do not confuse the object matcher.
def test_braces_inside_strings() -> None:
    text = 'Sure: {"s": "a } tricky { \\" string", "n": [1, 2]} trailing }'
    assert extract_json(text) == {"s": 'a } tricky { " string', "n": [1, 2]}


# Checks an unclosed brace is skipped in favour of a later valid object.
def test_unbalanced_first_brace_then_valid_object() -> None:
    assert extract_json('note { not closed\n then {"a": 1}') == {"a": 1}


# Checks text with no JSON object raises an error.
@pytest.mark.parametrize("text", ["no json here", "", "   ", "{ never closed"])
def test_no_json_raises(text: str) -> None:
    with pytest.raises(JSONExtractionError):
        extract_json(text)


# Checks a top-level JSON array is rejected.
def test_top_level_array_raises() -> None:
    with pytest.raises(JSONExtractionError, match="array"):
        extract_json('[{"a": 1}]')


# Checks invalid JSON between braces raises an error.
def test_invalid_json_inside_braces_raises() -> None:
    with pytest.raises(JSONExtractionError, match="invalid JSON"):
        extract_json("{'a': 1}")
