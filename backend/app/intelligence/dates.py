from __future__ import annotations

import calendar
import re
from dataclasses import dataclass

_MONTH_NUMBERS = {
    name: index
    for index in range(1, 13)
    for name in (calendar.month_name[index].lower(), calendar.month_abbr[index].lower())
}
_MONTH_NUMBERS["sept"] = 9
_MONTH = r"(?P<month>" + "|".join(sorted(_MONTH_NUMBERS, key=len, reverse=True)) + r")\.?"
_DAY = r"(?P<day>\d{1,2})(?:st|nd|rd|th)?"
_YEAR = r"(?:,?\s+(?P<year>\d{4}))?"

_ISO_RE = re.compile(r"\b(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})\b")
_NUMERIC_RE = re.compile(r"\b(?P<a>\d{1,2})[/.](?P<b>\d{1,2})[/.](?P<year>\d{2,4})\b")
_MONTH_DAY_RE = re.compile(rf"\b{_MONTH}\s+{_DAY}\b{_YEAR}", re.IGNORECASE)
_DAY_MONTH_RE = re.compile(rf"\b{_DAY}\s+(?:of\s+)?{_MONTH}\b{_YEAR}", re.IGNORECASE)


@dataclass(frozen=True)
class DateCheck:
    normalized: str | None = None
    invalid: bool = False
    reason: str | None = None


# Tells whether a day exists in the given month, assuming a leap year when the year is unknown.
def _valid_day(year: int | None, month: int, day: int) -> bool:
    if not 1 <= month <= 12 or day < 1:
        return False
    return day <= calendar.monthrange(year or 2024, month)[1]


# Builds an ISO date string when the year is known.
def _iso(year: int | None, month: int, day: int) -> str | None:
    return f"{year:04d}-{month:02d}-{day:02d}" if year else None


# Expands a two-digit year to four digits.
def _full_year(raw: str) -> int:
    year = int(raw)
    return year + 2000 if year < 100 else year


# Checks a date written in a document: flags impossible dates and normalizes full dates to ISO.
def check_date(text: str) -> DateCheck:
    for pattern in (_ISO_RE, _MONTH_DAY_RE, _DAY_MONTH_RE):
        match = pattern.search(text)
        if not match:
            continue
        parts = match.groupdict()
        raw_month = parts["month"]
        month = int(raw_month) if raw_month.isdigit() else _MONTH_NUMBERS[raw_month.lower()]
        day = int(parts["day"])
        year = int(parts["year"]) if parts.get("year") else None
        if not _valid_day(year, month, day):
            return DateCheck(invalid=True, reason=f"'{match.group(0)}' is not a real calendar date")
        return DateCheck(normalized=_iso(year, month, day))

    match = _NUMERIC_RE.search(text)
    if match:
        a, b, year = int(match["a"]), int(match["b"]), _full_year(match["year"])
        day_first = _valid_day(year, b, a)
        month_first = _valid_day(year, a, b)
        if not day_first and not month_first:
            return DateCheck(invalid=True, reason=f"'{match.group(0)}' is not a real calendar date")
        if day_first and month_first and a != b:
            return DateCheck(reason=f"'{match.group(0)}' is ambiguous (day/month order unclear)")
        return DateCheck(normalized=_iso(year, b, a) if day_first else _iso(year, a, b))
    return DateCheck()
