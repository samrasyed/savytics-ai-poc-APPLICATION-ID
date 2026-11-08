from __future__ import annotations

import re
from difflib import SequenceMatcher

_MONTHS = {
    "january": "jan",
    "february": "feb",
    "march": "mar",
    "april": "apr",
    "june": "jun",
    "july": "jul",
    "august": "aug",
    "september": "sep",
    "sept": "sep",
    "october": "oct",
    "november": "nov",
    "december": "dec",
}
_ORDINAL_RE = re.compile(r"\b(\d+)(?:st|nd|rd|th)\b")
_WORD_RE = re.compile(r"[a-z0-9]+")
_NAME_STOPWORDS = {"the", "a", "an", "of", "and", "team", "group", "dept", "department"}
_SIMILARITY_STOPWORDS = {"the", "a", "an", "to", "of", "and", "for", "on", "in", "with", "by"}


# Splits text into lowercase word tokens, unifying month names and dropping ordinal suffixes.
def tokens(text: str) -> list[str]:
    lowered = text.lower().replace("’", "'").replace("‘", "'")
    lowered = _ORDINAL_RE.sub(r"\1", lowered)
    return [_MONTHS.get(t, t) for t in _WORD_RE.findall(lowered)]


# Tells whether two short texts describe the same thing, by word overlap or containment.
def similar(a: str, b: str, threshold: float = 0.8) -> bool:
    ta = set(tokens(a)) - _SIMILARITY_STOPWORDS
    tb = set(tokens(b)) - _SIMILARITY_STOPWORDS
    if not ta or not tb:
        return False
    if ta == tb:
        return True
    small, large = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if len(small) >= 3 and small <= large:
        return True
    return len(ta & tb) / len(ta | tb) >= threshold


class SourceText:
    # Tokenizes a document once so it can be searched many times.
    def __init__(self, text: str) -> None:
        self.tokens = tokens(text)
        self.token_set = set(self.tokens)
        self._joined = " " + " ".join(self.tokens) + " "

    # Tells whether the phrase appears in the document as consecutive words.
    def contains_phrase(self, phrase: str) -> bool:
        words = tokens(phrase)
        return bool(words) and f" {' '.join(words)} " in self._joined

    # Tells whether a name or short value is mentioned in the document.
    def mentions(self, name: str) -> bool:
        if self.contains_phrase(name):
            return True
        significant = [t for t in tokens(name) if t not in _NAME_STOPWORDS and len(t) > 1]
        return bool(significant) and all(t in self.token_set for t in significant)

    # Rates how well a quoted sentence is supported by the document text.
    def evidence_status(self, evidence: str | None) -> str:
        if not evidence:
            return "missing"
        words = tokens(evidence)
        if not words:
            return "missing"
        if self.contains_phrase(evidence):
            return "verified"
        matcher = SequenceMatcher(None, words, self.tokens, autojunk=False)
        matched = sum(block.size for block in matcher.get_matching_blocks() if block.size >= 3)
        return "partial" if matched / len(words) >= 0.75 else "not_found"
