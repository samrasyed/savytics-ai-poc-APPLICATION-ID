from __future__ import annotations

from collections import Counter

from app.domain.schemas import (
    ENTITY_CATEGORIES,
    OPEN_QUESTIONS_MAX_ITEMS,
    ActionItem,
    AnalysisResult,
    Contradiction,
    Decision,
    Dependency,
    Entities,
    OpenQuestion,
    Risk,
    ValidationIssue,
    ValidationReport,
)
from app.intelligence.context import DocumentIndex
from app.intelligence.dates import check_date
from app.intelligence.text_match import SourceText, similar, tokens

_SUPPORTED = {"verified", "partial"}


class _Report:
    # Starts an empty set of counters and issues.
    def __init__(self) -> None:
        self.checks: Counter[str] = Counter()
        self.issues: list[ValidationIssue] = []

    # Records a problem or note found during validation.
    def add(self, module: str, message: str, level: str = "warning") -> None:
        self.issues.append(ValidationIssue(level=level, module=module, message=message))

    # Counts one evidence check by its outcome.
    def evidence(self, status: str) -> str:
        if status != "missing":
            self.checks["evidence_checked"] += 1
            self.checks[f"evidence_{'unverified' if status == 'not_found' else status}"] += 1
        return status

    # Freezes the collected counters and issues into the report model.
    def build(self) -> ValidationReport:
        return ValidationReport(checks=dict(self.checks), issues=self.issues)


# Labels an item as a fact, an inference or an assumption from its evidence and certainty.
def _basis(evidence_status: str, explicit: bool) -> str:
    if evidence_status not in _SUPPORTED:
        return "assumption"
    return "fact" if explicit else "inference"


# Removes entities that never appear in the document and checks date entities.
def _validate_entities(entities: Entities, source: SourceText, report: _Report) -> Entities:
    updates = {}
    for category in ENTITY_CATEGORIES:
        kept = []
        for entity in getattr(entities, category):
            if not source.mentions(entity.text):
                report.checks["entities_removed"] += 1
                report.add(
                    "entities",
                    f"Removed '{entity.text}' from {category.replace('_', ' ')}: "
                    "not found in the document.",
                    "info",
                )
                continue
            if category == "dates":
                check = check_date(entity.text)
                if check.invalid:
                    report.checks["invalid_dates"] += 1
                    report.add("entities", f"Date problem: {check.reason}.")
                entity = entity.model_copy(update={"normalized": check.normalized})
            kept.append(entity)
        updates[category] = kept
    return entities.model_copy(update=updates)


# Checks owners, deadlines and evidence for one task against the document.
def _check_action_item(item: ActionItem, source: SourceText, report: _Report) -> ActionItem:
    kept = [o for o in item.owners if source.mentions(o)]
    for owner in item.owners:
        if owner not in kept:
            report.checks["owners_removed"] += 1
            report.add(
                "action_items",
                f"Owner '{owner}' for \"{item.task}\" is not mentioned in the document "
                "and was removed.",
            )
    if kept != item.owners:
        item = item.with_owners(kept)

    updates: dict[str, object] = {}
    if item.due_date:
        if not source.mentions(item.due_date):
            report.checks["deadlines_removed"] += 1
            report.add(
                "action_items",
                f"Deadline '{item.due_date}' for \"{item.task}\" does not appear in the document "
                "and was removed.",
            )
            updates.update(due_date=None, deadline_type=None, due_date_iso=None)
        else:
            check = check_date(item.due_date)
            if check.invalid:
                report.checks["invalid_dates"] += 1
                report.add("action_items", f'Deadline problem for "{item.task}": {check.reason}.')
            elif check.reason:
                report.add("action_items", f'Deadline for "{item.task}": {check.reason}.', "info")
            updates["due_date_iso"] = check.normalized
    status = report.evidence(source.evidence_status(item.evidence))
    updates.update(evidence_status=status, basis=_basis(status, item.certainty == "high"))
    return item.model_copy(update=updates)


# Merges a duplicate task into the one already kept, filling in missing details.
def _merge_tasks(kept: ActionItem, duplicate: ActionItem) -> ActionItem:
    owners = [*kept.owners]
    for owner in duplicate.owners:
        if owner.casefold() not in {o.casefold() for o in owners}:
            owners.append(owner)
    merged = kept.with_owners(owners)
    updates: dict[str, object] = {}
    if not merged.due_date and duplicate.due_date:
        updates.update(
            due_date=duplicate.due_date,
            deadline_type=duplicate.deadline_type,
            due_date_iso=duplicate.due_date_iso,
        )
    if merged.evidence_status not in _SUPPORTED and duplicate.evidence_status in _SUPPORTED:
        updates.update(
            evidence=duplicate.evidence,
            evidence_status=duplicate.evidence_status,
            basis=duplicate.basis,
        )
    return merged.model_copy(update=updates)


# Validates every task and merges near-duplicate tasks.
def _validate_action_items(
    items: list[ActionItem], source: SourceText, report: _Report
) -> list[ActionItem]:
    out: list[ActionItem] = []
    for raw in items:
        item = _check_action_item(raw, source, report)
        match = next((i for i, k in enumerate(out) if similar(k.task, item.task)), None)
        if match is None:
            out.append(item)
            continue
        report.checks["duplicates_merged"] += 1
        report.add(
            "action_items",
            f'Merged duplicate task "{item.task}" into "{out[match].task}".',
            "info",
        )
        out[match] = _merge_tasks(out[match], item)
    return out


# Checks decision makers and evidence, and merges duplicate decisions.
def _validate_decisions(
    decisions: list[Decision], source: SourceText, report: _Report
) -> list[Decision]:
    out: list[Decision] = []
    for decision in decisions:
        updates: dict[str, object] = {}
        if decision.decision_maker and not source.mentions(decision.decision_maker):
            report.checks["owners_removed"] += 1
            report.add(
                "decisions",
                f"Decision maker '{decision.decision_maker}' is not mentioned in the document "
                "and was removed.",
            )
            updates["decision_maker"] = None
        status = report.evidence(source.evidence_status(decision.evidence))
        updates.update(evidence_status=status, basis=_basis(status, True))
        decision = decision.model_copy(update=updates)
        if any(similar(d.description, decision.description) for d in out):
            report.checks["duplicates_merged"] += 1
            report.add("decisions", f'Merged duplicate decision "{decision.description}".', "info")
            continue
        out.append(decision)
    return out


# Tells whether a gap of this category is already covered for the given item.
def _covered(questions: list[OpenQuestion], category: str, subject: str) -> bool:
    for q in questions:
        if q.category != category:
            continue
        if q.related_to and similar(q.related_to, subject, 0.6):
            return True
        subject_words = set(tokens(subject))
        if (
            subject_words
            and len(subject_words & set(tokens(q.question))) / len(subject_words) >= 0.7
        ):
            return True
    return False


# Checks question evidence and adds questions for gaps found in tasks and decisions.
def _validate_questions(
    questions: list[OpenQuestion],
    items: list[ActionItem],
    decisions: list[Decision],
    source: SourceText,
    report: _Report,
) -> list[OpenQuestion]:
    out: list[OpenQuestion] = []
    for question in questions:
        if question.origin == "check":
            continue
        status = source.evidence_status(question.evidence)
        if question.evidence:
            report.evidence(status)
        out.append(question.model_copy(update={"evidence_status": status}))

    added: list[OpenQuestion] = []
    for item in items:
        if not item.owners and not _covered(out, "missing_owner", item.task):
            added.append(
                OpenQuestion(
                    question=f'Who is responsible for "{item.task}"?',
                    category="missing_owner",
                    related_to=item.task,
                    origin="check",
                )
            )
        needs_deadline = not item.due_date and item.status != "done"
        if needs_deadline and not _covered(out, "missing_deadline", item.task):
            added.append(
                OpenQuestion(
                    question=f'When is "{item.task}" due?',
                    category="missing_deadline",
                    related_to=item.task,
                    origin="check",
                )
            )
    for decision in decisions:
        if decision.status == "pending" and not _covered(
            out, "unresolved_decision", decision.description
        ):
            added.append(
                OpenQuestion(
                    question=f'Has a final decision been made on "{decision.description}"?',
                    category="unresolved_decision",
                    related_to=decision.description,
                    origin="check",
                )
            )
        if decision.status == "proposed" and not _covered(
            out, "missing_approval", decision.description
        ):
            added.append(
                OpenQuestion(
                    question=f'Has "{decision.description}" been approved, and by whom?',
                    category="missing_approval",
                    related_to=decision.description,
                    origin="check",
                )
            )
    room = max(0, OPEN_QUESTIONS_MAX_ITEMS - len(out))
    report.checks["questions_added"] += min(room, len(added))
    return [*out, *added[:room]]


# Keeps only conflicts with at least two different, quote-backed values involving this document.
def _validate_contradictions(
    contradictions: list[Contradiction], index: DocumentIndex, report: _Report
) -> list[Contradiction]:
    out: list[Contradiction] = []
    for conflict in contradictions:
        values = []
        for value in conflict.values:
            doc = index.by_id(value.document_id)
            status = report.evidence(doc.source.evidence_status(value.evidence))
            if status in _SUPPORTED:
                values.append(value.model_copy(update={"evidence_status": status}))
        distinct = {" ".join(tokens(v.value)) for v in values}
        if len(distinct) < 2:
            report.checks["items_dropped"] += 1
            report.add(
                "contradictions",
                f'Dropped "{conflict.description}": fewer than two different values '
                "backed by a quote from the documents.",
                "info",
            )
            continue
        if not any(v.is_current for v in values):
            report.checks["items_dropped"] += 1
            report.add(
                "contradictions",
                f'Dropped "{conflict.description}": it does not involve this document.',
                "info",
            )
            continue
        cross = any(not v.is_current for v in values)
        out.append(
            conflict.model_copy(
                update={
                    "values": values,
                    "scope": "cross_document" if cross else "within_document",
                }
            )
        )
    return out


# Verifies risk evidence and labels each risk as a fact, inference or assumption.
def _validate_risks(risks: list[Risk], index: DocumentIndex, report: _Report) -> list[Risk]:
    out: list[Risk] = []
    for risk in risks:
        doc = index.by_id(risk.document_id)
        status = report.evidence(doc.source.evidence_status(risk.evidence))
        if any(similar(r.description, risk.description) for r in out):
            report.checks["duplicates_merged"] += 1
            continue
        out.append(
            risk.model_copy(
                update={
                    "evidence_status": status,
                    "basis": _basis(status, risk.origin == "explicit"),
                }
            )
        )
    return out


# Keeps only dependencies whose supporting quote is found in the document.
def _validate_dependencies(
    dependencies: list[Dependency], source: SourceText, report: _Report
) -> list[Dependency]:
    out: list[Dependency] = []
    for dependency in dependencies:
        status = report.evidence(source.evidence_status(dependency.evidence))
        if status not in _SUPPORTED:
            report.checks["items_dropped"] += 1
            report.add(
                "dependencies",
                f'Dropped "{dependency.dependent_task}" depends on "{dependency.source_task}": '
                "no supporting sentence in the document.",
                "info",
            )
            continue
        if similar(dependency.source_task, dependency.dependent_task, 0.9):
            report.checks["items_dropped"] += 1
            continue
        out.append(dependency.model_copy(update={"evidence_status": status}))
    return out


# Runs every validation check and returns the cleaned result with its validation report.
def validate(result: AnalysisResult, index: DocumentIndex) -> AnalysisResult:
    report = _Report()
    source = index.current.source
    entities = _validate_entities(result.entities, source, report)
    items = _validate_action_items(result.action_items, source, report)
    decisions = _validate_decisions(result.decisions, source, report)
    questions = _validate_questions(result.open_question_details, items, decisions, source, report)
    contradictions = _validate_contradictions(result.contradictions, index, report)
    risks = _validate_risks(result.risks, index, report)
    dependencies = _validate_dependencies(result.dependencies, source, report)
    return result.model_copy(
        update={
            "entities": entities,
            "action_items": items,
            "decisions": decisions,
            "open_question_details": questions,
            "open_questions": [q.question for q in questions],
            "contradictions": contradictions,
            "risks": risks,
            "dependencies": dependencies,
            "validation": report.build(),
        }
    )
