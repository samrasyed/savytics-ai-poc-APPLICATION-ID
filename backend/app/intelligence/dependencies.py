from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.domain.schemas import DEPENDENCIES_MAX_ITEMS, Dependency
from app.intelligence.context import DocumentIndex

KEY = "dependencies"

SCHEMA = """"dependencies": [
    {"source_task": "the task that must happen first", "dependent_task": "the task that waits for it",
     "description": "string", "evidence": "exact quote from D0"}
  ]"""

RULES = """DEPENDENCIES
- A dependency means one task cannot start or finish until another task or deliverable is ready. Example: "Testing depends on API readiness".
- Report a dependency only when the current document (D0) states it or clearly implies it with words like "after", "once", "depends on", "blocked by", "requires", "before".
- Do not assume dependencies from typical project order. If the text does not support it, leave it out.
- Either side may be a task from the extracted tasks list or another step named in the document, such as QA testing, deployment or launch. Use the task wording from the list where it matches.
- evidence must be an exact quote from D0."""


# Converts the model's raw dependencies into validated records, skipping self-references.
def parse(raw: Any, index: DocumentIndex) -> list[Dependency]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("dependencies must be a list")
    out: list[Dependency] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            dependency = Dependency.model_validate(item)
        except ValidationError:
            continue
        if dependency.source_task.casefold() != dependency.dependent_task.casefold():
            out.append(dependency)
    return out[:DEPENDENCIES_MAX_ITEMS]
