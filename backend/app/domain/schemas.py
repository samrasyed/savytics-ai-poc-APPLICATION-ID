from __future__ import annotations

import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    ValidationError,
    field_validator,
    model_validator,
)

logger = logging.getLogger(__name__)

SUMMARY_MAX = 1500
TASK_MAX = 500
OWNER_MAX = 100
OWNER_FIELD_MAX = 300
DUE_DATE_MAX = 100
LIST_ITEM_MAX = 500
EVIDENCE_MAX = 600
ENTITY_TEXT_MAX = 200
ENTITY_CONTEXT_MAX = 300
KEY_POINTS_MAX_ITEMS = 15
ACTION_ITEMS_MAX_ITEMS = 40
OPEN_QUESTIONS_MAX_ITEMS = 25
ENTITY_MAX_ITEMS = 30
DECISIONS_MAX_ITEMS = 25
CONTRADICTIONS_MAX_ITEMS = 20
RISKS_MAX_ITEMS = 20
DEPENDENCIES_MAX_ITEMS = 30
SUMMARY_PREVIEW_CHARS = 160

_PLACEHOLDERS = {
    "",
    "null",
    "none",
    "n/a",
    "na",
    "unknown",
    "unassigned",
    "not specified",
    "not stated",
    "tbd",
}

EvidenceStatus = Literal["verified", "partial", "not_found", "missing"]
Basis = Literal["fact", "inference", "assumption"]

M = TypeVar("M", bound=BaseModel)


# Tells whether a value is a real number (bools are excluded).
def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# Cuts text to the limit at a word boundary, adds an ellipsis and logs a warning.
def truncate_words(text: str, limit: int, *, field: str) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    space = cut.rfind(" ")
    if space > limit // 2:
        cut = cut[:space]
    logger.warning("normalization: truncated field=%s from=%d to_limit=%d", field, len(text), limit)
    return cut.rstrip() + "…"


# Turns placeholder values like "n/a" into None and trims the rest to the limit.
def _clean_optional(value: Any, limit: int, field: str) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, str):
        if not _is_number(value):
            return None
        value = str(value)
    value = value.strip()
    if value.lower() in _PLACEHOLDERS:
        return None
    return truncate_words(value, limit, field=field)


# Cleans a required text field: numbers become text, whitespace is stripped and length capped.
def _clean_required(value: Any, limit: int, field: str) -> Any:
    if _is_number(value):
        value = str(value)
    if isinstance(value, str):
        return truncate_words(value.strip(), limit, field=field)
    return value


# Cleans a list of strings: drops blanks and duplicates, trims items and caps the length.
def _clean_str_list(value: Any, *, field: str, max_items: int) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    seen: set[str] = set()
    out: list[str] = []
    for item in value:
        if item is None:
            continue
        if not isinstance(item, str):
            if _is_number(item):
                item = str(item)
            else:
                continue
        item = item.strip()
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(truncate_words(item, LIST_ITEM_MAX, field=field))
    if len(out) > max_items:
        logger.warning(
            "normalization: truncated list field=%s from=%d to=%d", field, len(out), max_items
        )
        out = out[:max_items]
    return out


# Maps a free-text label onto one allowed value, using synonyms, or returns the default.
def _choice(
    value: Any, allowed: set[str], default: Any = None, synonyms: dict[str, str] | None = None
) -> Any:
    if not isinstance(value, str):
        return default
    key = value.strip().lower().replace("-", "_").replace(" ", "_")
    if key in allowed:
        return key
    if synonyms and key in synonyms:
        return synonyms[key]
    return default


# Validates each list item on its own, skipping bad items and duplicates instead of failing.
def _lenient_items(
    value: Any,
    model: type[M],
    *,
    field: str,
    max_items: int,
    text_key: str,
    key: Any = None,
) -> list[M]:
    if value is None:
        return []
    if isinstance(value, (str, dict, BaseModel)):
        value = [value]
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    out: list[M] = []
    seen: set[str] = set()
    dropped = 0
    for item in value:
        if isinstance(item, model):
            parsed = item
        else:
            if isinstance(item, str) or _is_number(item):
                item = {text_key: str(item)}
            if not isinstance(item, dict):
                dropped += 1
                continue
            try:
                parsed = model.model_validate(item)
            except ValidationError:
                dropped += 1
                continue
        dedupe_key = (key(parsed) if key else str(getattr(parsed, text_key))).casefold()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        out.append(parsed)
    if dropped:
        logger.warning("normalization: dropped invalid items field=%s count=%d", field, dropped)
    if len(out) > max_items:
        logger.warning(
            "normalization: truncated list field=%s from=%d to=%d", field, len(out), max_items
        )
        out = out[:max_items]
    return out


# Serializes a datetime as a UTC ISO string ending in "Z".
def _to_utc_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


UTCDateTime = Annotated[datetime, PlainSerializer(_to_utc_z, return_type=str, when_used="json")]


class AnalyzeRequest(BaseModel):
    title: str
    text: str

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "Sprint planning",
                    "text": "Meeting transcript... Priya will draft pricing by Friday.",
                }
            ]
        }
    )


class CredentialsRequest(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=1024)

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"email": "you@example.com", "password": "a-long-password"}]
        }
    )


class UserOut(BaseModel):
    id: str
    email: str
    created_at: UTCDateTime


class AuthResponse(BaseModel):
    token: str
    user: UserOut


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Entity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str = Field(min_length=1, max_length=ENTITY_TEXT_MAX)
    context: str | None = Field(default=None, max_length=ENTITY_CONTEXT_MAX)
    normalized: str | None = None

    # Accepts "name" or "value" as the entity text.
    @model_validator(mode="before")
    @classmethod
    def _aliases(cls, data: Any) -> Any:
        if isinstance(data, dict) and "text" not in data:
            data = dict(data)
            data["text"] = data.get("name") or data.get("value")
        return data

    # Strips and trims the entity text.
    @field_validator("text", mode="before")
    @classmethod
    def _text(cls, value: Any) -> Any:
        return _clean_required(value, ENTITY_TEXT_MAX, "entities.text")

    # Cleans the optional context note.
    @field_validator("context", mode="before")
    @classmethod
    def _context(cls, value: Any) -> str | None:
        return _clean_optional(value, ENTITY_CONTEXT_MAX, "entities.context")


ENTITY_CATEGORIES = (
    "people",
    "organizations",
    "dates",
    "locations",
    "technologies",
    "monetary_values",
    "important_terms",
)

_ENTITY_ALIASES = {
    "persons": "people",
    "names": "people",
    "orgs": "organizations",
    "organisations": "organizations",
    "companies": "organizations",
    "deadlines": "dates",
    "places": "locations",
    "tools": "technologies",
    "tech": "technologies",
    "money": "monetary_values",
    "amounts": "monetary_values",
    "monetary": "monetary_values",
    "terms": "important_terms",
    "key_terms": "important_terms",
    "concepts": "important_terms",
}


class Entities(BaseModel):
    model_config = ConfigDict(extra="ignore")

    people: list[Entity] = Field(default_factory=list)
    organizations: list[Entity] = Field(default_factory=list)
    dates: list[Entity] = Field(default_factory=list)
    locations: list[Entity] = Field(default_factory=list)
    technologies: list[Entity] = Field(default_factory=list)
    monetary_values: list[Entity] = Field(default_factory=list)
    important_terms: list[Entity] = Field(default_factory=list)

    # Maps alternative category names (e.g. "orgs", "money") onto the standard ones.
    @model_validator(mode="before")
    @classmethod
    def _category_aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return {}
        out: dict[str, Any] = {}
        for raw_key, items in data.items():
            if not isinstance(raw_key, str):
                continue
            key = raw_key.strip().lower().replace(" ", "_")
            key = _ENTITY_ALIASES.get(key, key)
            if key in ENTITY_CATEGORIES:
                existing = out.get(key) or []
                out[key] = [*existing, *(items if isinstance(items, list) else [items])]
        return out

    # Validates each category's entities leniently and removes duplicates.
    @field_validator(*ENTITY_CATEGORIES, mode="before")
    @classmethod
    def _items(cls, value: Any, info: Any) -> list[Entity]:
        if not isinstance(value, list):
            value = [] if value is None else [value]
        return _lenient_items(
            value,
            Entity,
            field=f"entities.{info.field_name}",
            max_items=ENTITY_MAX_ITEMS,
            text_key="text",
        )

    # Counts all entities across categories.
    def count(self) -> int:
        return sum(len(getattr(self, c)) for c in ENTITY_CATEGORIES)


_STATUS_SYNONYMS = {
    "todo": "open",
    "to_do": "open",
    "pending": "open",
    "not_started": "open",
    "planned": "open",
    "assigned": "open",
    "ongoing": "in_progress",
    "started": "in_progress",
    "in_review": "in_progress",
    "completed": "done",
    "complete": "done",
    "finished": "done",
    "on_hold": "blocked",
    "stuck": "blocked",
}

_CERTAINTY_SYNONYMS = {"certain": "high", "likely": "medium", "uncertain": "low", "possible": "low"}
_SOURCE_SYNONYMS = {"stated": "explicit", "implied": "inferred", "ai": "inferred"}


class ActionItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task: str = Field(min_length=1, max_length=TASK_MAX)
    owner: str | None = Field(default=None, max_length=OWNER_FIELD_MAX)
    owners: list[str] = Field(default_factory=list)
    due_date: str | None = Field(default=None, max_length=DUE_DATE_MAX)
    deadline_type: Literal["confirmed", "tentative"] | None = None
    due_date_iso: str | None = None
    status: Literal["open", "in_progress", "done", "blocked", "unknown"] = "open"
    priority: Priority | None = None
    priority_source: Literal["explicit", "inferred"] | None = None
    certainty: Literal["high", "medium", "low"] = "medium"
    evidence: str | None = Field(default=None, max_length=EVIDENCE_MAX)
    evidence_status: EvidenceStatus = "missing"
    basis: Basis | None = None

    # Merges the single "owner" field into "owners" and accepts "deadline" for "due_date".
    @model_validator(mode="before")
    @classmethod
    def _merge_owner_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if data.get("due_date") is None and data.get("deadline") is not None:
            data["due_date"] = data["deadline"]
        raw = data.get("owners")
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, list) or not raw:
            raw = [data.get("owner")]
        owners: list[str] = []
        for item in raw:
            name = _clean_optional(item, OWNER_MAX, "action_items.owners")
            if name and name.casefold() not in {o.casefold() for o in owners}:
                owners.append(name)
        data["owners"] = owners
        data["owner"] = ", ".join(owners) or None
        return data

    # Converts numbers to text, strips whitespace and trims the task to its limit.
    @field_validator("task", mode="before")
    @classmethod
    def _task(cls, value: Any) -> Any:
        return _clean_required(value, TASK_MAX, "action_items.task")

    # Cleans the combined owner text and turns placeholders into None.
    @field_validator("owner", mode="before")
    @classmethod
    def _owner(cls, value: Any) -> str | None:
        return _clean_optional(value, OWNER_FIELD_MAX, "action_items.owner")

    # Cleans the due date field and turns placeholders into None.
    @field_validator("due_date", mode="before")
    @classmethod
    def _due_date(cls, value: Any) -> str | None:
        return _clean_optional(value, DUE_DATE_MAX, "action_items.due_date")

    # Normalizes the deadline type to confirmed or tentative.
    @field_validator("deadline_type", mode="before")
    @classmethod
    def _deadline_type(cls, value: Any) -> str | None:
        return _choice(
            value,
            {"confirmed", "tentative"},
            synonyms={
                "firm": "confirmed",
                "fixed": "confirmed",
                "explicit": "confirmed",
                "estimated": "tentative",
                "approximate": "tentative",
                "proposed": "tentative",
            },
        )

    # Normalizes the task status, using "unknown" for unrecognized values.
    @field_validator("status", mode="before")
    @classmethod
    def _status(cls, value: Any) -> str:
        if value is None:
            return "open"
        return _choice(
            value,
            {"open", "in_progress", "done", "blocked", "unknown"},
            "unknown",
            _STATUS_SYNONYMS,
        )

    # Lowercases the priority and drops anything that is not low, medium or high.
    @field_validator("priority", mode="before")
    @classmethod
    def _priority(cls, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, Priority):
            return value.value
        if not isinstance(value, str):
            return None
        value = value.strip().lower()
        if value in _PLACEHOLDERS:
            return None
        if value not in {p.value for p in Priority}:
            logger.warning("normalization: unknown priority dropped")
            return None
        return value

    # Normalizes where the priority came from: stated in the text or inferred.
    @field_validator("priority_source", mode="before")
    @classmethod
    def _priority_source(cls, value: Any) -> str | None:
        return _choice(value, {"explicit", "inferred"}, synonyms=_SOURCE_SYNONYMS)

    # Normalizes the certainty level, defaulting to medium.
    @field_validator("certainty", mode="before")
    @classmethod
    def _certainty(cls, value: Any) -> str:
        return _choice(value, {"high", "medium", "low"}, "medium", _CERTAINTY_SYNONYMS)

    # Cleans the supporting quote.
    @field_validator("evidence", mode="before")
    @classmethod
    def _evidence(cls, value: Any) -> str | None:
        return _clean_optional(value, EVIDENCE_MAX, "action_items.evidence")

    # Clears dependent fields when there is no deadline or priority to describe.
    @model_validator(mode="after")
    def _consistency(self) -> ActionItem:
        if self.due_date is None:
            self.deadline_type = None
            self.due_date_iso = None
        if self.priority is None:
            self.priority_source = None
        elif self.priority_source is None:
            self.priority_source = "inferred"
        return self

    # Returns a copy with a new owners list and the matching combined owner text.
    def with_owners(self, owners: list[str]) -> ActionItem:
        joined = ", ".join(owners) or None
        if joined:
            joined = truncate_words(joined, OWNER_FIELD_MAX, field="action_items.owner")
        return self.model_copy(update={"owners": owners, "owner": joined})


_DECISION_SYNONYMS = {
    "approved": "confirmed",
    "agreed": "confirmed",
    "final": "confirmed",
    "decided": "confirmed",
    "suggested": "proposed",
    "suggestion": "proposed",
    "declined": "rejected",
    "deferred": "pending",
    "postponed": "pending",
    "undecided": "pending",
    "open": "pending",
    "revised": "changed",
    "updated": "changed",
    "reversed": "changed",
}


class Decision(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str = Field(min_length=1, max_length=TASK_MAX)
    decision_maker: str | None = Field(default=None, max_length=OWNER_MAX)
    status: Literal["confirmed", "proposed", "rejected", "pending", "changed"] = "proposed"
    previous_decision: str | None = Field(default=None, max_length=TASK_MAX)
    evidence: str | None = Field(default=None, max_length=EVIDENCE_MAX)
    evidence_status: EvidenceStatus = "missing"
    basis: Basis | None = None

    # Accepts "decision" as an alias for the description.
    @model_validator(mode="before")
    @classmethod
    def _aliases(cls, data: Any) -> Any:
        if isinstance(data, dict) and "description" not in data:
            data = dict(data)
            data["description"] = data.get("decision")
        return data

    # Strips and trims the decision description.
    @field_validator("description", mode="before")
    @classmethod
    def _description(cls, value: Any) -> Any:
        return _clean_required(value, TASK_MAX, "decisions.description")

    # Cleans the decision maker and turns placeholders into None.
    @field_validator("decision_maker", mode="before")
    @classmethod
    def _maker(cls, value: Any) -> str | None:
        return _clean_optional(value, OWNER_MAX, "decisions.decision_maker")

    # Normalizes the decision status, treating unclear values as proposed rather than confirmed.
    @field_validator("status", mode="before")
    @classmethod
    def _status(cls, value: Any) -> str:
        return _choice(
            value,
            {"confirmed", "proposed", "rejected", "pending", "changed"},
            "proposed",
            _DECISION_SYNONYMS,
        )

    # Cleans the optional text fields.
    @field_validator("previous_decision", "evidence", mode="before")
    @classmethod
    def _optional_text(cls, value: Any) -> str | None:
        return _clean_optional(value, EVIDENCE_MAX, "decisions.text")

    # Marks a confirmed decision that replaces an earlier decision as changed.
    @model_validator(mode="after")
    def _changed_when_replacing(self) -> Decision:
        if self.status == "confirmed" and self.previous_decision:
            self.status = "changed"
        return self


OPEN_QUESTION_CATEGORIES = {
    "missing_deadline",
    "missing_owner",
    "unresolved_decision",
    "unclear_responsibility",
    "missing_approval",
    "unanswered_question",
}


class OpenQuestion(BaseModel):
    model_config = ConfigDict(extra="ignore")

    question: str = Field(min_length=1, max_length=LIST_ITEM_MAX)
    category: Literal[
        "missing_deadline",
        "missing_owner",
        "unresolved_decision",
        "unclear_responsibility",
        "missing_approval",
        "unanswered_question",
    ] = "unanswered_question"
    related_to: str | None = Field(default=None, max_length=TASK_MAX)
    evidence: str | None = Field(default=None, max_length=EVIDENCE_MAX)
    evidence_status: EvidenceStatus = "missing"
    origin: Literal["document", "check"] = "document"

    # Accepts "text" as an alias for the question.
    @model_validator(mode="before")
    @classmethod
    def _aliases(cls, data: Any) -> Any:
        if isinstance(data, dict) and "question" not in data:
            data = dict(data)
            data["question"] = data.get("text")
        return data

    # Strips and trims the question text.
    @field_validator("question", mode="before")
    @classmethod
    def _question(cls, value: Any) -> Any:
        return _clean_required(value, LIST_ITEM_MAX, "open_questions.question")

    # Normalizes the gap category, defaulting to an unanswered question.
    @field_validator("category", mode="before")
    @classmethod
    def _category(cls, value: Any) -> str:
        return _choice(value, OPEN_QUESTION_CATEGORIES, "unanswered_question")

    # Cleans the optional text fields.
    @field_validator("related_to", "evidence", mode="before")
    @classmethod
    def _optional_text(cls, value: Any) -> str | None:
        return _clean_optional(value, EVIDENCE_MAX, "open_questions.text")


class ConflictValue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    value: str = Field(min_length=1, max_length=LIST_ITEM_MAX)
    document_id: str | None = None
    document_title: str | None = None
    is_current: bool = True
    evidence: str | None = Field(default=None, max_length=EVIDENCE_MAX)
    evidence_status: EvidenceStatus = "missing"

    # Strips and trims the conflicting value.
    @field_validator("value", mode="before")
    @classmethod
    def _value(cls, value: Any) -> Any:
        return _clean_required(value, LIST_ITEM_MAX, "contradictions.value")

    # Cleans the supporting quote.
    @field_validator("evidence", mode="before")
    @classmethod
    def _evidence(cls, value: Any) -> str | None:
        return _clean_optional(value, EVIDENCE_MAX, "contradictions.evidence")


class Contradiction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str = Field(min_length=1, max_length=TASK_MAX)
    conflict_type: Literal["date", "deadline", "owner", "decision", "amount", "scope", "other"] = (
        "other"
    )
    scope: Literal["within_document", "cross_document"] = "within_document"
    values: list[ConflictValue] = Field(default_factory=list)
    resolution_status: Literal["unresolved", "resolved"] = "unresolved"
    suggested_action: str | None = Field(default=None, max_length=TASK_MAX)

    # Strips and trims the conflict description.
    @field_validator("description", mode="before")
    @classmethod
    def _description(cls, value: Any) -> Any:
        return _clean_required(value, TASK_MAX, "contradictions.description")

    # Normalizes the conflict type.
    @field_validator("conflict_type", mode="before")
    @classmethod
    def _type(cls, value: Any) -> str:
        return _choice(
            value,
            {"date", "deadline", "owner", "decision", "amount", "scope", "other"},
            "other",
            {"ownership": "owner", "money": "amount", "budget": "amount", "timeline": "date"},
        )

    # Normalizes the resolution status, defaulting to unresolved.
    @field_validator("resolution_status", mode="before")
    @classmethod
    def _resolution(cls, value: Any) -> str:
        return _choice(value, {"unresolved", "resolved"}, "unresolved")

    # Validates each conflicting value leniently.
    @field_validator("values", mode="before")
    @classmethod
    def _values(cls, value: Any) -> list[ConflictValue]:
        return _lenient_items(
            value,
            ConflictValue,
            field="contradictions.values",
            max_items=10,
            text_key="value",
            key=lambda v: f"{v.value}|{v.document_id}|{v.evidence}",
        )

    # Cleans the suggested next step.
    @field_validator("suggested_action", mode="before")
    @classmethod
    def _action(cls, value: Any) -> str | None:
        return _clean_optional(value, TASK_MAX, "contradictions.suggested_action")


_RISK_CATEGORIES = {
    "delay",
    "resources",
    "dependency",
    "approval",
    "technical",
    "financial",
    "other",
}


class Risk(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str = Field(min_length=1, max_length=TASK_MAX)
    category: Literal[
        "delay", "resources", "dependency", "approval", "technical", "financial", "other"
    ] = "other"
    severity: Literal["high", "medium", "low"] = "medium"
    severity_source: Literal["explicit", "inferred"] = "inferred"
    origin: Literal["explicit", "inferred"] = "inferred"
    reason: str | None = Field(default=None, max_length=TASK_MAX)
    evidence: str | None = Field(default=None, max_length=EVIDENCE_MAX)
    evidence_status: EvidenceStatus = "missing"
    document_id: str | None = None
    document_title: str | None = None
    is_current: bool = True
    resolution_status: Literal["unresolved", "mitigated", "resolved"] = "unresolved"
    mitigation: str | None = Field(default=None, max_length=TASK_MAX)
    basis: Basis | None = None

    # Strips and trims the risk description.
    @field_validator("description", mode="before")
    @classmethod
    def _description(cls, value: Any) -> Any:
        return _clean_required(value, TASK_MAX, "risks.description")

    # Normalizes the risk category.
    @field_validator("category", mode="before")
    @classmethod
    def _category(cls, value: Any) -> str:
        return _choice(
            value,
            _RISK_CATEGORIES,
            "other",
            {
                "project_delay": "delay",
                "schedule": "delay",
                "missing_resources": "resources",
                "resource": "resources",
                "unresolved_dependency": "dependency",
                "unconfirmed_approval": "approval",
                "technical_blocker": "technical",
                "blocker": "technical",
                "financial_risk": "financial",
                "budget": "financial",
            },
        )

    # Normalizes the severity, defaulting to medium.
    @field_validator("severity", mode="before")
    @classmethod
    def _severity(cls, value: Any) -> str:
        return _choice(value, {"high", "medium", "low"}, "medium")

    # Normalizes whether a value was stated or inferred, defaulting to inferred.
    @field_validator("severity_source", "origin", mode="before")
    @classmethod
    def _source(cls, value: Any) -> str:
        return _choice(value, {"explicit", "inferred"}, "inferred", _SOURCE_SYNONYMS)

    # Normalizes the resolution status, defaulting to unresolved.
    @field_validator("resolution_status", mode="before")
    @classmethod
    def _resolution(cls, value: Any) -> str:
        return _choice(value, {"unresolved", "mitigated", "resolved"}, "unresolved")

    # Cleans the optional text fields.
    @field_validator("reason", "evidence", "mitigation", mode="before")
    @classmethod
    def _optional_text(cls, value: Any) -> str | None:
        return _clean_optional(value, EVIDENCE_MAX, "risks.text")

    # Keeps severity marked as inferred whenever the risk itself was inferred.
    @model_validator(mode="after")
    def _consistency(self) -> Risk:
        if self.origin == "inferred":
            self.severity_source = "inferred"
        return self


class Dependency(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source_task: str = Field(min_length=1, max_length=TASK_MAX)
    dependent_task: str = Field(min_length=1, max_length=TASK_MAX)
    description: str | None = Field(default=None, max_length=TASK_MAX)
    evidence: str | None = Field(default=None, max_length=EVIDENCE_MAX)
    evidence_status: EvidenceStatus = "missing"

    # Strips and trims the task names.
    @field_validator("source_task", "dependent_task", mode="before")
    @classmethod
    def _tasks(cls, value: Any) -> Any:
        return _clean_required(value, TASK_MAX, "dependencies.task")

    # Cleans the optional text fields.
    @field_validator("description", "evidence", mode="before")
    @classmethod
    def _optional_text(cls, value: Any) -> str | None:
        return _clean_optional(value, EVIDENCE_MAX, "dependencies.text")


class ValidationIssue(BaseModel):
    level: Literal["warning", "info"] = "info"
    module: str
    message: str


class ValidationReport(BaseModel):
    checks: dict[str, int] = Field(default_factory=dict)
    issues: list[ValidationIssue] = Field(default_factory=list)


ModuleState = Literal["ok", "failed", "not_run"]


class IntelligenceStatus(BaseModel):
    status: Literal["complete", "partial", "failed", "disabled", "not_run"] = "not_run"
    modules: dict[str, ModuleState] = Field(default_factory=dict)
    message: str | None = None
    documents_compared: int = 0


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str = Field(min_length=1, max_length=SUMMARY_MAX)
    key_points: list[str] = Field(default_factory=list, max_length=KEY_POINTS_MAX_ITEMS)
    entities: Entities = Field(default_factory=Entities)
    action_items: list[ActionItem] = Field(default_factory=list, max_length=ACTION_ITEMS_MAX_ITEMS)
    decisions: list[Decision] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list, max_length=OPEN_QUESTIONS_MAX_ITEMS)
    open_question_details: list[OpenQuestion] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)
    validation: ValidationReport = Field(default_factory=ValidationReport)
    intelligence: IntelligenceStatus = Field(default_factory=IntelligenceStatus)

    # Fills in empty lists for missing fields and splits question objects from question text.
    @model_validator(mode="before")
    @classmethod
    def _defaults_for_missing_lists(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        for field in ("key_points", "action_items", "open_questions"):
            if data.get(field) is None:
                logger.warning("normalization: missing list field=%s defaulted to []", field)
                data[field] = []
        if data.get("entities") is not None and not isinstance(data["entities"], dict):
            logger.warning("normalization: entities was not an object; ignored")
            data["entities"] = {}
        questions = data["open_questions"]
        if data.get("open_question_details") is None and isinstance(questions, list):
            data["open_question_details"] = questions
            data["open_questions"] = [
                q.get("question", q.get("text")) if isinstance(q, dict) else q for q in questions
            ]
        return data

    # Requires a non-empty summary and trims it to its limit.
    @field_validator("summary", mode="before")
    @classmethod
    def _summary(cls, value: Any) -> Any:
        if not isinstance(value, str):
            raise ValueError("summary must be a non-empty string")
        value = value.strip()
        if not value:
            raise ValueError("summary must be a non-empty string")
        return truncate_words(value, SUMMARY_MAX, field="summary")

    # Cleans the key points list.
    @field_validator("key_points", mode="before")
    @classmethod
    def _key_points(cls, value: Any) -> list[str]:
        return _clean_str_list(value, field="key_points", max_items=KEY_POINTS_MAX_ITEMS)

    # Cleans the open questions list.
    @field_validator("open_questions", mode="before")
    @classmethod
    def _open_questions(cls, value: Any) -> list[str]:
        return _clean_str_list(value, field="open_questions", max_items=OPEN_QUESTIONS_MAX_ITEMS)

    # Accepts plain-string tasks, drops empty or duplicate tasks and caps the list length.
    @field_validator("action_items", mode="before")
    @classmethod
    def _action_items(cls, value: Any) -> list[ActionItem]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("action_items must be a list")
        candidates: list[Any] = []
        for item in value:
            if isinstance(item, str):
                item = {"task": item}
            elif isinstance(item, ActionItem):
                item = item.model_dump()
            if not isinstance(item, dict):
                continue
            task = item.get("task")
            if _is_number(task):
                task = str(task)
            if not isinstance(task, str) or not task.strip():
                continue
            candidates.append(item)
        return _lenient_items(
            candidates,
            ActionItem,
            field="action_items",
            max_items=ACTION_ITEMS_MAX_ITEMS,
            text_key="task",
        )

    # Validates decisions leniently and removes duplicates.
    @field_validator("decisions", mode="before")
    @classmethod
    def _decisions(cls, value: Any) -> list[Decision]:
        return _lenient_items(
            value,
            Decision,
            field="decisions",
            max_items=DECISIONS_MAX_ITEMS,
            text_key="description",
        )

    # Validates structured open questions leniently and removes duplicates.
    @field_validator("open_question_details", mode="before")
    @classmethod
    def _question_details(cls, value: Any) -> list[OpenQuestion]:
        return _lenient_items(
            value,
            OpenQuestion,
            field="open_question_details",
            max_items=OPEN_QUESTIONS_MAX_ITEMS,
            text_key="question",
        )

    # Validates contradictions leniently.
    @field_validator("contradictions", mode="before")
    @classmethod
    def _contradictions(cls, value: Any) -> list[Contradiction]:
        return _lenient_items(
            value,
            Contradiction,
            field="contradictions",
            max_items=CONTRADICTIONS_MAX_ITEMS,
            text_key="description",
        )

    # Validates risks leniently.
    @field_validator("risks", mode="before")
    @classmethod
    def _risks(cls, value: Any) -> list[Risk]:
        return _lenient_items(
            value, Risk, field="risks", max_items=RISKS_MAX_ITEMS, text_key="description"
        )

    # Validates dependencies leniently and removes duplicate pairs.
    @field_validator("dependencies", mode="before")
    @classmethod
    def _dependencies(cls, value: Any) -> list[Dependency]:
        return _lenient_items(
            value,
            Dependency,
            field="dependencies",
            max_items=DEPENDENCIES_MAX_ITEMS,
            text_key="source_task",
            key=lambda d: f"{d.source_task}->{d.dependent_task}",
        )

    # Keeps the plain open-question list and the structured details in sync.
    @model_validator(mode="after")
    def _sync_questions(self) -> AnalysisResult:
        if self.open_question_details:
            self.open_questions = [q.question for q in self.open_question_details]
        elif self.open_questions:
            self.open_question_details = [OpenQuestion(question=q) for q in self.open_questions]
        return self


class AnalysisRecord(BaseModel):
    id: str
    title: str
    input_text: str
    result: AnalysisResult
    provider: str
    model: str
    prompt_version: str
    latency_ms: int
    created_at: UTCDateTime


class AnalysisListItem(BaseModel):
    id: str
    title: str
    created_at: UTCDateTime
    summary_preview: str
    action_item_count: int


class AnalysisListResponse(BaseModel):
    items: list[AnalysisListItem]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    provider: str
    model: str
    mock_mode: bool
    prompt_version: str
    database: Literal["ok", "error"]
    version: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool
    request_id: str
    details: Any = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
