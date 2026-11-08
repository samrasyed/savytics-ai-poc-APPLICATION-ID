from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.domain.schemas import RISKS_MAX_ITEMS, Risk
from app.intelligence.context import DocumentIndex

KEY = "risks"

SCHEMA = """"risks": [
    {"description": "string", "category": "delay | resources | dependency | approval | technical | financial | other",
     "severity": "high | medium | low", "severity_source": "explicit | inferred", "origin": "explicit | inferred",
     "reason": "string", "evidence": "exact quote", "source": "D0 | D1 | ...",
     "resolution_status": "unresolved | mitigated | resolved", "mitigation": "string"}
  ]"""

RULES = """RISKS
- Look for project delays, missing resources, unresolved dependencies, unconfirmed approvals, technical blockers and financial risks.
- origin: "explicit" if the text itself names it as a risk, blocker, concern or problem; "inferred" if you are deducing it from the facts.
- severity: your assessment of impact. severity_source is "explicit" only when the text itself states how serious it is (for example "critical", "major blocker"); otherwise "inferred". An inferred risk always has an inferred severity.
- reason: one sentence explaining why it is a risk. evidence: an exact quote that supports it.
- resolution_status: "mitigated" or "resolved" only if the text says so; otherwise "unresolved".
- mitigation: a short, practical suggestion. Do not present it as something the document decided."""


# Converts the model's raw risks into validated records with resolved document sources.
def parse(raw: Any, index: DocumentIndex) -> list[Risk]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("risks must be a list")
    out: list[Risk] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        doc = index.resolve(item.get("source") or item.get("document")) or index.current
        try:
            out.append(
                Risk.model_validate(
                    {
                        **item,
                        "document_id": doc.document_id,
                        "document_title": doc.title,
                        "is_current": doc.is_current,
                    }
                )
            )
        except ValidationError:
            continue
    return out[:RISKS_MAX_ITEMS]
