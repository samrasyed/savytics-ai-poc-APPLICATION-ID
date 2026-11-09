from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

try:
    import psycopg
except ImportError:
    psycopg = None

SCHEMA_VERSION = 2

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS analyses (
    id             TEXT PRIMARY KEY,
    title          TEXT NOT NULL,
    input_text     TEXT NOT NULL,
    result_json    TEXT NOT NULL,
    provider       TEXT NOT NULL,
    model          TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    latency_ms     INTEGER NOT NULL,
    created_at     TEXT NOT NULL,
    user_id        TEXT
);
CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses (created_at DESC);

CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions (user_id);
"""

USER_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_analyses_user ON analyses (user_id, created_at DESC)"
)

DB_ERRORS: tuple[type[Exception], ...] = (sqlite3.Error,) + ((psycopg.Error,) if psycopg else ())
INTEGRITY_ERRORS: tuple[type[Exception], ...] = (sqlite3.IntegrityError,) + (
    (psycopg.IntegrityError,) if psycopg else ()
)

_PG_SCHEMES = ("postgres://", "postgresql://")


# Tells whether a database target is a Postgres connection URL rather than a SQLite path.
def is_postgres(target: str) -> bool:
    return target.startswith(_PG_SCHEMES)


# Rewrites SQLite-style SQL (? placeholders, IS ?, rowid) into its Postgres equivalent.
def _to_postgres(sql: str) -> str:
    sql = re.sub(r"\bIS \?", "IS NOT DISTINCT FROM ?", sql)
    sql = sql.replace("rowid DESC", "id DESC")
    return sql.replace("?", "%s")


class _Row(dict):
    # Stores the column values so the row can be read by name or by position.
    def __init__(self, names: list[str], values: tuple[Any, ...]) -> None:
        super().__init__(zip(names, values, strict=True))
        self._values = values

    # Returns a column by position when given an int, otherwise by name.
    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


# Builds psycopg rows that behave like sqlite3.Row.
def _row_factory(cursor: Any) -> Any:
    names = [col.name for col in cursor.description or []]
    return lambda values: _Row(names, values)


class PgConnection:
    # Wraps a psycopg connection so it offers the small sqlite3 API the app uses.
    def __init__(self, url: str) -> None:
        if psycopg is None:
            raise RuntimeError("DATABASE_URL is set but psycopg is not installed")
        self._conn = psycopg.connect(
            url, row_factory=_row_factory, prepare_threshold=None, connect_timeout=10
        )

    # Runs one SQLite-style statement on Postgres and returns its cursor.
    def execute(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> Any:
        return self._conn.execute(_to_postgres(sql), tuple(params))

    # Commits the current transaction.
    def commit(self) -> None:
        self._conn.commit()

    # Closes the connection, discarding any uncommitted work.
    def close(self) -> None:
        self._conn.close()


Connection = sqlite3.Connection | PgConnection


# Opens a Postgres connection for a URL, or a SQLite connection with WAL and a busy timeout.
def connect(target: str) -> Connection:
    if is_postgres(target):
        return PgConnection(target)
    conn = sqlite3.connect(target, timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


# Adds the user_id column to an analyses table created before accounts existed.
def _migrate(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(analyses)")}
    if "user_id" not in columns:
        conn.execute("ALTER TABLE analyses ADD COLUMN user_id TEXT")
    conn.execute(USER_INDEX_SQL)


# Creates the Postgres tables under a lock so parallel cold starts do not collide.
def _init_postgres(url: str) -> None:
    conn = PgConnection(url)
    try:
        conn.execute("SELECT pg_advisory_xact_lock(724001)")
        for statement in SCHEMA_SQL.split(";"):
            if statement.strip():
                conn.execute(statement)
        conn.execute(USER_INDEX_SQL)
        conn.commit()
    finally:
        conn.close()


# Creates the database tables if they do not exist yet, then applies migrations.
def init_db(target: str) -> None:
    if is_postgres(target):
        _init_postgres(target)
        return
    Path(target).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    conn = connect(target)
    try:
        conn.executescript(SCHEMA_SQL)
        _migrate(conn)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
    finally:
        conn.close()
