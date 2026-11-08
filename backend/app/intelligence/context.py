from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

from app.domain.schemas import AnalysisRecord, AnalysisResult
from app.intelligence.text_match import SourceText
from app.prompts.analysis_prompt import escape_delimiters

PREVIOUS_DOC_MAX_CHARS = 3000


@dataclass
class DocumentContext:
    label: str
    document_id: str
    title: str
    text: str
    is_current: bool
    result: AnalysisResult | None = None

    # Tokenized text used for evidence checks, built on first use.
    @cached_property
    def source(self) -> SourceText:
        return SourceText(self.text)


@dataclass
class DocumentIndex:
    current: DocumentContext
    previous: list[DocumentContext] = field(default_factory=list)

    # Returns every document, current first.
    @property
    def all(self) -> list[DocumentContext]:
        return [self.current, *self.previous]

    # Finds a document by its label (D0, D1…), ID or exact title.
    def resolve(self, ref: object) -> DocumentContext | None:
        if ref is None:
            return None
        key = str(ref).strip()
        lowered = key.lower()
        if lowered in {"current", "this", "this document", "current document"}:
            return self.current
        for doc in self.all:
            if lowered in {doc.label.lower(), doc.document_id.lower()} or key == doc.title:
                return doc
        return None

    # Finds a document by its ID, falling back to the current document.
    def by_id(self, document_id: str | None) -> DocumentContext:
        for doc in self.all:
            if doc.document_id == document_id:
                return doc
        return self.current


# Builds the index of the current document and the previous analyses it is compared with.
def build_index(
    document_id: str, title: str, text: str, previous: list[AnalysisRecord]
) -> DocumentIndex:
    current = DocumentContext("D0", document_id, title, text, is_current=True)
    others = [
        DocumentContext(f"D{i}", r.id, r.title, r.input_text, is_current=False, result=r.result)
        for i, r in enumerate(previous, start=1)
    ]
    return DocumentIndex(current, others)


# Writes a compact, quote-backed fact sheet for a previous document to include in the prompt.
def describe_previous(doc: DocumentContext) -> str:
    result = doc.result
    lines = [f"[{doc.label}] Title: {escape_delimiters(doc.title)}"]
    if result is not None:
        for item in result.action_items:
            owner = item.owner or "unassigned"
            due = item.due_date or "no deadline"
            quote = f' | quote: "{item.evidence}"' if item.evidence else ""
            lines.append(f"- task: {item.task} | owner: {owner} | deadline: {due}{quote}")
        for decision in result.decisions:
            quote = f' | quote: "{decision.evidence}"' if decision.evidence else ""
            lines.append(f"- decision ({decision.status}): {decision.description}{quote}")
        for entity in result.entities.dates:
            lines.append(f"- date: {entity.text} ({entity.context or 'no context'})")
        for entity in result.entities.monetary_values:
            lines.append(f"- amount: {entity.text} ({entity.context or 'no context'})")
    text = "\n".join(lines)
    if len(text) > PREVIOUS_DOC_MAX_CHARS:
        text = text[:PREVIOUS_DOC_MAX_CHARS].rsplit("\n", 1)[0]
    return escape_delimiters(text)
