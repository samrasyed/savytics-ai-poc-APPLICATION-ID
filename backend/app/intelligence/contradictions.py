from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.domain.schemas import CONTRADICTIONS_MAX_ITEMS, Contradiction
from app.intelligence.context import DocumentIndex

KEY = "contradictions"

SCHEMA = """"contradictions": [
    {"description": "string", "conflict_type": "date | deadline | owner | decision | amount | scope | other",
     "values": [{"value": "string", "source": "D0 | D1 | ...", "evidence": "exact quote from that document"}],
     "resolution_status": "unresolved | resolved", "suggested_action": "string"}
  ]"""

RULES = """CONTRADICTIONS
- Report a contradiction only when two or more statements give DIFFERENT values for the SAME thing: the same project's launch date, the same task's deadline, the same task's owner, the same budget, or a decision that reverses an earlier decision.
- Dates or values that belong to different events are NOT contradictions. Example: testing on December 8 and launch on December 15 refer to different events, so do not report them.
- Check within the current document (D0) and between D0 and the previous documents (D1, D2...). Every contradiction must involve D0.
- Each value needs its source label and an exact quote from that source. For previous documents, quote only from the facts provided for them.
- Never decide which value is correct. Set resolution_status to "resolved" only if the text itself explicitly settles the conflict.
- suggested_action: a neutral next step, for example "Confirm the launch date with the project owner"."""


# Converts the model's raw contradictions into validated records with resolved document sources.
def parse(raw: Any, index: DocumentIndex) -> list[Contradiction]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("contradictions must be a list")
    out: list[Contradiction] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        values = []
        for value in item.get("values") or []:
            if not isinstance(value, dict):
                continue
            doc = index.resolve(value.get("source") or value.get("document"))
            if doc is None:
                continue
            values.append(
                {
                    "value": value.get("value"),
                    "document_id": doc.document_id,
                    "document_title": doc.title,
                    "is_current": doc.is_current,
                    "evidence": value.get("evidence"),
                }
            )
        try:
            contradiction = Contradiction.model_validate({**item, "values": values})
        except ValidationError:
            continue
        cross = any(not v.is_current for v in contradiction.values)
        out.append(
            contradiction.model_copy(
                update={"scope": "cross_document" if cross else "within_document"}
            )
        )
    return out[:CONTRADICTIONS_MAX_ITEMS]
