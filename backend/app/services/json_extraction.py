from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```[ \t]*(?:json|JSON)?[ \t]*\r?\n?(.*?)```", re.DOTALL)


class JSONExtractionError(ValueError):
    pass


# Returns the first balanced {...} block in the text, ignoring braces inside strings.
def _find_balanced_object(text: str) -> str | None:
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        start = text.find("{", start + 1)
    return None


# Pulls one JSON object out of raw model text, handling code fences and surrounding prose.
def extract_json(content: str) -> dict[str, Any]:
    if content is None:
        raise JSONExtractionError("empty response")
    text = content.lstrip("﻿").strip()
    if not text:
        raise JSONExtractionError("empty response")

    fence = _FENCE_RE.search(text)
    if fence:
        text = fence.group(1).strip()

    if not text.startswith("{"):
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                raise JSONExtractionError("expected a JSON object, got an array")
        candidate = _find_balanced_object(text)
        if candidate is None:
            raise JSONExtractionError("no JSON object found in the response")
        text = candidate

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        candidate = _find_balanced_object(text)
        if candidate is None or candidate == text:
            raise JSONExtractionError(f"invalid JSON: {exc.msg} at position {exc.pos}") from exc
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as exc2:
            raise JSONExtractionError(f"invalid JSON: {exc2.msg} at position {exc2.pos}") from exc2

    if not isinstance(data, dict):
        raise JSONExtractionError(f"expected a JSON object, got {type(data).__name__}")
    return data
