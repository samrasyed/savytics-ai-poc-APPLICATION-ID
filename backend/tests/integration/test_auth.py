from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.database import connect, init_db
from app.services.auth_service import AuthService, hash_password, verify_password
from tests.conftest import authenticate

CREDS = {"email": "Priya@Example.com", "password": "correct-horse"}


# Checks registering returns a token and a user with a normalised email.
def test_register_returns_token_and_user(anon_client: TestClient) -> None:
    resp = anon_client.post("/api/auth/register", json=CREDS)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["token"]
    assert body["user"]["email"] == "priya@example.com"
    assert "password" not in resp.text


# Checks the same email cannot register twice, whatever its case.
def test_register_duplicate_email(anon_client: TestClient) -> None:
    anon_client.post("/api/auth/register", json=CREDS)
    resp = anon_client.post("/api/auth/register", json={**CREDS, "email": "PRIYA@example.com"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "EMAIL_TAKEN"


# Checks bad emails and short passwords are rejected with a validation error.
@pytest.mark.parametrize(
    "creds",
    [{"email": "nope", "password": "correct-horse"}, {"email": "a@b.co", "password": "short"}],
)
def test_register_validation(anon_client: TestClient, creds: dict[str, str]) -> None:
    resp = anon_client.post("/api/auth/register", json=creds)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


# Checks login works with the right password and fails alike for a wrong one or unknown email.
def test_login(anon_client: TestClient) -> None:
    anon_client.post("/api/auth/register", json=CREDS)
    ok = anon_client.post("/api/auth/login", json={**CREDS, "email": " priya@example.com "})
    assert ok.status_code == 200
    me = anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {ok.json()['token']}"})
    assert me.json()["email"] == "priya@example.com"
    for creds in ({**CREDS, "password": "wrong-horse"}, {**CREDS, "email": "x@example.com"}):
        bad = anon_client.post("/api/auth/login", json=creds)
        assert bad.status_code == 401
        assert bad.json()["error"]["code"] == "INVALID_CREDENTIALS"


# Checks analysis endpoints and /me need a valid token.
@pytest.mark.parametrize("header", [None, "Bearer not-a-real-token", "Basic abc"])
def test_protected_routes_need_token(anon_client: TestClient, header: str | None) -> None:
    headers = {"Authorization": header} if header else {}
    for resp in (
        anon_client.get("/api/analyses", headers=headers),
        anon_client.post("/api/analyses", json={"title": "t", "text": "x"}, headers=headers),
        anon_client.get("/api/auth/me", headers=headers),
    ):
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "AUTH_REQUIRED"


# Checks logging out stops the token from working.
def test_logout_revokes_token(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


# Checks one user cannot list, read or delete another user's analyses.
def test_analyses_are_private(app: FastAPI) -> None:
    with TestClient(app) as alice, TestClient(app) as bob:
        authenticate(alice)
        authenticate(bob)
        created = alice.post(
            "/api/analyses", json={"title": "Mine", "text": "Priya drafts."}
        ).json()
        assert bob.get("/api/analyses").json()["total"] == 0
        assert bob.get(f"/api/analyses/{created['id']}").status_code == 404
        assert bob.delete(f"/api/analyses/{created['id']}").status_code == 404
        assert alice.get(f"/api/analyses/{created['id']}").status_code == 200


# Checks the health endpoint stays public.
def test_health_is_public(anon_client: TestClient) -> None:
    assert anon_client.get("/api/health").status_code == 200


# Checks password hashes verify only the right password and never contain it.
def test_password_hashing() -> None:
    stored = hash_password("correct-horse")
    assert "correct-horse" not in stored
    assert verify_password("correct-horse", stored)
    assert not verify_password("wrong-horse", stored)
    assert not verify_password("correct-horse", "garbage")


# Checks an expired session is refused.
def test_expired_session(db_path: str) -> None:
    init_db(db_path)
    conn = connect(db_path)
    try:
        start = datetime(2026, 1, 1, tzinfo=UTC)
        token = AuthService(conn, 1, now=lambda: start).register("a@b.co", "correct-horse").token
        later = AuthService(conn, 1, now=lambda: start + timedelta(days=2))
        with pytest.raises(Exception, match="log in"):
            later.user_for_token(token)
    finally:
        conn.close()


# Checks a database made before accounts existed gains the user_id column.
def test_migration_adds_user_column(db_path: str) -> None:
    from pathlib import Path

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    old = sqlite3.connect(db_path)
    old.execute(
        "CREATE TABLE analyses (id TEXT PRIMARY KEY, title TEXT NOT NULL, input_text TEXT NOT NULL,"
        " result_json TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,"
        " prompt_version TEXT NOT NULL, latency_ms INTEGER NOT NULL, created_at TEXT NOT NULL)"
    )
    old.commit()
    old.close()
    init_db(db_path)
    conn = connect(db_path)
    try:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(analyses)")}
    finally:
        conn.close()
    assert "user_id" in cols
