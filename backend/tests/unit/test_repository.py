from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.db.database import SCHEMA_VERSION, connect, init_db
from app.db.repository import AnalysisRepository
from app.domain.errors import InternalError
from app.domain.schemas import AnalysisRecord, AnalysisResult
from tests.conftest import VALID_RESULT

BASE = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)


# Builds a sample record with a creation time offset by i minutes.
def make_record(i: int = 0, title: str = "Doc") -> AnalysisRecord:
    return AnalysisRecord(
        id=str(uuid.uuid4()),
        title=f"{title} {i}",
        input_text="text",
        result=AnalysisResult.model_validate(VALID_RESULT),
        provider="mock",
        model="mock-analyzer-v1",
        prompt_version="analysis-v1",
        latency_ms=12,
        created_at=BASE + timedelta(minutes=i),
    )


# Checks a saved record can be loaded back unchanged.
def test_save_and_get(repository: AnalysisRepository) -> None:
    record = make_record()
    repository.save(record)
    assert repository.get(record.id) == record
    assert repository.get(str(uuid.uuid4())) is None


# Checks the list is newest first with the right total and pages.
def test_list_newest_first_with_total_and_pagination(repository: AnalysisRepository) -> None:
    records = [make_record(i) for i in range(5)]
    for r in records:
        repository.save(r)
    items, total = repository.list(limit=2, offset=0)
    assert total == 5
    assert [i.id for i in items] == [records[4].id, records[3].id]
    items, _ = repository.list(limit=2, offset=4)
    assert [i.id for i in items] == [records[0].id]
    assert items[0].action_item_count == 1
    assert items[0].summary_preview == VALID_RESULT["summary"][:160]


# Checks delete reports whether a row was removed.
def test_delete(repository: AnalysisRepository) -> None:
    record = make_record()
    repository.save(record)
    assert repository.delete(record.id) is True
    assert repository.delete(record.id) is False


# Checks a corrupt row makes get fail and is skipped by list.
def test_corrupt_row_get_raises_and_list_skips(
    repository: AnalysisRepository, db_path: str, caplog: pytest.LogCaptureFixture
) -> None:
    good, bad = make_record(0), make_record(1)
    repository.save(good)
    repository.save(bad)
    conn = connect(db_path)
    conn.execute("UPDATE analyses SET result_json = ? WHERE id = ?", ('{"bad": true}', bad.id))
    conn.commit()
    conn.close()

    with pytest.raises(InternalError):
        repository.get(bad.id)
    items, total = repository.list(10, 0)
    assert [i.id for i in items] == [good.id]
    assert total == 2
    assert "corrupt" in caplog.text


# Checks init_db can run twice and sets the schema version and WAL mode.
def test_init_db_is_idempotent_and_sets_version(tmp_path) -> None:
    path = str(tmp_path / "nested" / "dir" / "x.db")
    init_db(path)
    init_db(path)
    conn = connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    conn.close()


# Checks ping succeeds on an open connection and fails on a closed one.
def test_ping(repository: AnalysisRepository, db_path: str) -> None:
    assert repository.ping() is True
    conn = connect(db_path)
    conn.close()
    assert AnalysisRepository(conn).ping() is False


# Checks SQL-like input is stored safely through parameterized queries.
def test_parameterized_queries_resist_injection(repository: AnalysisRepository) -> None:
    record = make_record(title="x'); DROP TABLE analyses; --")
    repository.save(record)
    assert repository.get(record.id) is not None
    with pytest.raises(sqlite3.Error):
        repository._conn.execute("SELECT * FROM missing_table")


# Checks recent returns newest records first and skips the excluded one.
def test_recent_excludes_and_orders(repository: AnalysisRepository) -> None:
    records = [make_record(i) for i in range(4)]
    for r in records:
        repository.save(r)
    recent = repository.recent(2, exclude_id=records[3].id)
    assert [r.id for r in recent] == [records[2].id, records[1].id]
    assert repository.recent(0) == []


# Checks recent skips corrupt rows.
def test_recent_skips_corrupt_rows(repository: AnalysisRepository, db_path: str) -> None:
    good, bad = make_record(0), make_record(1)
    repository.save(good)
    repository.save(bad)
    conn = connect(db_path)
    conn.execute("UPDATE analyses SET result_json = '{}' WHERE id = ?", (bad.id,))
    conn.commit()
    conn.close()
    assert [r.id for r in repository.recent(5)] == [good.id]


# Checks update_result replaces the stored result and reports missing rows.
def test_update_result(repository: AnalysisRepository) -> None:
    record = make_record()
    repository.save(record)
    new_result = AnalysisResult.model_validate({"summary": "Updated."})
    assert repository.update_result(record.id, new_result) is True
    assert repository.get(record.id).result.summary == "Updated."
    assert repository.update_result(str(uuid.uuid4()), new_result) is False
