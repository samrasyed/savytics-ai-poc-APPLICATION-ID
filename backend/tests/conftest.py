from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.db.database import connect, init_db
from app.db.repository import AnalysisRepository
from app.main import create_app
from app.providers.base import LLMMessage, ProviderResponse

VALID_RESULT: dict[str, Any] = {
    "summary": "The team agreed the sprint scope. Billing ships first.",
    "key_points": ["Billing redesign is top priority.", "Export timeout affects 8% of accounts."],
    "action_items": [
        {"task": "Draft pricing copy", "owner": "Priya", "due_date": "Friday", "priority": "high"}
    ],
    "open_questions": ["Who owns the design review?"],
}


# Returns the valid sample result as JSON, with optional field overrides.
def valid_json(**overrides: Any) -> str:
    return json.dumps({**VALID_RESULT, **overrides})


class FakeProvider:
    name = "fake"

    # Stores the scripted replies and starts empty call logs.
    def __init__(self, script: list[Any], model: str = "fake-model") -> None:
        self.script = list(script)
        self.model = model
        self.calls: list[list[LLMMessage]] = []
        self.json_modes: list[bool] = []

    # Records the call and returns or raises the next scripted item.
    def complete(self, messages: list[LLMMessage], *, json_mode: bool) -> ProviderResponse:
        self.calls.append([dict(m) for m in messages])
        self.json_modes.append(json_mode)
        if not self.script:
            raise AssertionError("FakeProvider script exhausted")
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, ProviderResponse):
            return item
        return ProviderResponse(
            content=item,
            model=self.model,
            finish_reason="stop",
            prompt_tokens=10,
            completion_tokens=20,
        )


class RecordingSleep:
    # Starts with an empty list of recorded delays.
    def __init__(self) -> None:
        self.delays: list[float] = []

    # Records the requested delay instead of actually sleeping.
    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


# Gives each test its own temporary database path.
@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "data" / "analyses.db")


# Builds mock-mode test settings that ignore any .env file.
@pytest.fixture
def settings(db_path: str) -> Settings:
    return Settings(
        _env_file=None,
        APP_ENV="test",
        LLM_PROVIDER="mock",
        DATABASE_PATH=db_path,
        MOCK_LATENCY_MS=0,
    )


# Provides a sleep recorder so retries do not really wait.
@pytest.fixture
def sleep() -> RecordingSleep:
    return RecordingSleep()


# Creates a test app wired to the recording sleep.
@pytest.fixture
def app(settings: Settings, sleep: RecordingSleep) -> FastAPI:
    application = create_app(settings)
    application.state.sleep = sleep
    return application


# Registers a fresh account on the client and sends its token with every later request.
def authenticate(c: TestClient, email: str | None = None) -> dict[str, Any]:
    email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
    resp = c.post("/api/auth/register", json={"email": email, "password": "correct-horse"})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    c.headers["Authorization"] = f"Bearer {body['token']}"
    return body


# Starts the app and yields a logged-in test client for it.
@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        authenticate(c)
        yield c


# Starts the app and yields a test client with no session.
@pytest.fixture
def anon_client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


# Yields a repository on a freshly initialized test database.
@pytest.fixture
def repository(db_path: str) -> Iterator[AnalysisRepository]:
    init_db(db_path)
    conn = connect(db_path)
    try:
        yield AnalysisRepository(conn)
    finally:
        conn.close()
