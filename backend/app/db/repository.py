from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from app.db.database import DB_ERRORS, Connection
from app.domain.errors import InternalError
from app.domain.schemas import (
    SUMMARY_PREVIEW_CHARS,
    AnalysisListItem,
    AnalysisRecord,
    AnalysisResult,
)

logger = logging.getLogger(__name__)


# Formats a datetime as a fixed-width UTC string so text order matches time order.
def _iso(dt: datetime) -> str:
    dt = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


class AnalysisRepository:
    # Stores the connection and the owner whose analyses this repository can see and change.
    def __init__(self, conn: Connection, user_id: str | None = None) -> None:
        self._conn = conn
        self._user_id = user_id

    # Inserts a new analysis record.
    def save(self, record: AnalysisRecord) -> None:
        self._conn.execute(
            """
            INSERT INTO analyses (id, title, input_text, result_json, provider, model,
                                  prompt_version, latency_ms, created_at, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.title,
                record.input_text,
                record.result.model_dump_json(),
                record.provider,
                record.model,
                record.prompt_version,
                record.latency_ms,
                _iso(record.created_at),
                self._user_id,
            ),
        )
        self._conn.commit()

    # Turns a database row into an analysis record.
    @staticmethod
    def _row_to_record(row: Any) -> AnalysisRecord:
        result = AnalysisResult.model_validate(json.loads(row["result_json"]))
        return AnalysisRecord(
            id=row["id"],
            title=row["title"],
            input_text=row["input_text"],
            result=result,
            provider=row["provider"],
            model=row["model"],
            prompt_version=row["prompt_version"],
            latency_ms=row["latency_ms"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # Loads one analysis by ID, or returns None if it does not exist.
    def get(self, analysis_id: str) -> AnalysisRecord | None:
        row = self._conn.execute(
            "SELECT * FROM analyses WHERE id = ? AND user_id IS ?", (analysis_id, self._user_id)
        ).fetchone()
        if row is None:
            return None
        try:
            return self._row_to_record(row)
        except (ValueError, ValidationError, TypeError) as exc:
            logger.error("corrupt analysis row id=%s error=%s", analysis_id, type(exc).__name__)
            raise InternalError() from None

    # Returns the newest analyses other than the excluded one, skipping corrupt rows.
    def recent(self, limit: int, exclude_id: str | None = None) -> list[AnalysisRecord]:
        if limit <= 0:
            return []
        rows = self._conn.execute(
            """
            SELECT * FROM analyses WHERE id != ? AND user_id IS ?
            ORDER BY created_at DESC, rowid DESC
            LIMIT ?
            """,
            (exclude_id or "", self._user_id, limit),
        ).fetchall()
        records: list[AnalysisRecord] = []
        for row in rows:
            try:
                records.append(self._row_to_record(row))
            except (ValueError, ValidationError, TypeError) as exc:
                logger.error(
                    "corrupt analysis row skipped id=%s error=%s", row["id"], type(exc).__name__
                )
        return records

    # Replaces the stored result of an analysis and reports whether a row was updated.
    def update_result(self, analysis_id: str, result: AnalysisResult) -> bool:
        cur = self._conn.execute(
            "UPDATE analyses SET result_json = ? WHERE id = ? AND user_id IS ?",
            (result.model_dump_json(), analysis_id, self._user_id),
        )
        self._conn.commit()
        return cur.rowcount > 0

    # Returns a page of analysis summaries, newest first, plus the total row count.
    def list(self, limit: int, offset: int) -> tuple[list[AnalysisListItem], int]:
        total = self._conn.execute(
            "SELECT COUNT(*) FROM analyses WHERE user_id IS ?", (self._user_id,)
        ).fetchone()[0]
        rows = self._conn.execute(
            """
            SELECT id, title, result_json, created_at FROM analyses WHERE user_id IS ?
            ORDER BY created_at DESC, rowid DESC
            LIMIT ? OFFSET ?
            """,
            (self._user_id, limit, offset),
        ).fetchall()
        items: list[AnalysisListItem] = []
        for row in rows:
            try:
                result = AnalysisResult.model_validate(json.loads(row["result_json"]))
                items.append(
                    AnalysisListItem(
                        id=row["id"],
                        title=row["title"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        summary_preview=result.summary[:SUMMARY_PREVIEW_CHARS],
                        action_item_count=len(result.action_items),
                    )
                )
            except (ValueError, ValidationError, TypeError) as exc:
                logger.error(
                    "corrupt analysis row skipped id=%s error=%s", row["id"], type(exc).__name__
                )
        return items, int(total)

    # Deletes one analysis and reports whether a row was removed.
    def delete(self, analysis_id: str) -> bool:
        cur = self._conn.execute(
            "DELETE FROM analyses WHERE id = ? AND user_id IS ?", (analysis_id, self._user_id)
        )
        self._conn.commit()
        return cur.rowcount > 0

    # Checks that the database answers a trivial query.
    def ping(self) -> bool:
        try:
            self._conn.execute("SELECT 1").fetchone()
            return True
        except DB_ERRORS:
            return False
