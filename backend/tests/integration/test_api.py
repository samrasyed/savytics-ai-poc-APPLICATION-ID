from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import FakeProvider, RecordingSleep, authenticate, valid_json

TEXT = "Meeting transcript. Priya will draft pricing by Friday."


# Posts an analysis request with the given title and text.
def post(client: TestClient, text: str = TEXT, title: str = "Sprint planning", **kw):
    return client.post("/api/analyses", json={"title": title, "text": text}, **kw)


# Checks a response is a standard error envelope with the expected values.
def assert_envelope(resp, status: int, code: str, retryable: bool) -> dict:
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert set(body) == {"error"}
    err = body["error"]
    assert err["code"] == code
    assert err["retryable"] is retryable
    assert err["message"]
    assert err["request_id"] == resp.headers["x-request-id"]
    assert "Traceback" not in resp.text
    return err


# Checks a successful POST returns 201 with the full record and headers.
def test_post_returns_201_full_shape(client: TestClient) -> None:
    resp = post(client, headers={"X-Request-ID": "abc-123"})
    assert resp.status_code == 201
    body = resp.json()
    assert resp.headers["location"] == f"/api/analyses/{body['id']}"
    assert resp.headers["x-request-id"] == "abc-123"
    assert set(body) == {
        "id",
        "title",
        "input_text",
        "result",
        "provider",
        "model",
        "prompt_version",
        "latency_ms",
        "created_at",
    }
    assert set(body["result"]) == {
        "summary",
        "key_points",
        "entities",
        "action_items",
        "decisions",
        "open_questions",
        "open_question_details",
        "contradictions",
        "risks",
        "dependencies",
        "validation",
        "intelligence",
    }
    assert body["result"]["intelligence"]["status"] == "complete"
    assert body["provider"] == "mock"
    assert body["model"] == "mock-analyzer-v1"
    assert body["prompt_version"] == "analysis-v2"
    assert body["created_at"].endswith("Z")
    uuid.UUID(body["id"])


# Checks an invalid X-Request-ID is replaced with a generated UUID.
def test_invalid_request_id_is_replaced(client: TestClient) -> None:
    resp = client.get("/api/health", headers={"X-Request-ID": "bad id!" + "x" * 80})
    rid = resp.headers["x-request-id"]
    assert rid != "bad id!"
    uuid.UUID(rid)


# Checks blank title or text returns EMPTY_INPUT.
@pytest.mark.parametrize(("title", "text"), [("T", ""), ("T", "   \n "), ("", "text")])
def test_empty_input(client: TestClient, title: str, text: str) -> None:
    assert_envelope(post(client, text=text, title=title), 422, "EMPTY_INPUT", False)


# Checks text over the limit returns INPUT_TOO_LONG with both numbers.
def test_too_long_text(client: TestClient) -> None:
    err = assert_envelope(post(client, text="x" * 50_001), 422, "INPUT_TOO_LONG", False)
    assert "50001" in err["message"] and "50000" in err["message"]


# Checks a missing field returns VALIDATION_ERROR without echoing input.
def test_missing_field_validation_error(client: TestClient) -> None:
    resp = client.post("/api/analyses", json={"title": "secret-title-value"})
    err = assert_envelope(resp, 422, "VALIDATION_ERROR", False)
    assert err["details"] == [{"field": "text", "reason": "Field required"}]
    assert "secret-title-value" not in resp.text


# Checks a malformed JSON body returns VALIDATION_ERROR.
def test_invalid_json_body(client: TestClient) -> None:
    resp = client.post(
        "/api/analyses", content=b"{not json", headers={"Content-Type": "application/json"}
    )
    assert_envelope(resp, 422, "VALIDATION_ERROR", False)


# Checks a body with a large Content-Length is rejected with 413.
def test_oversized_body_413(client: TestClient) -> None:
    resp = post(client, text="x" * 300_000)
    assert_envelope(resp, 413, "PAYLOAD_TOO_LARGE", False)


# Checks a streamed body that grows past the limit is rejected with 413.
def test_oversized_streamed_body_413(settings: Settings) -> None:
    app = create_app(settings.model_copy(update={"MAX_BODY_BYTES": 100}))
    with TestClient(app) as c:
        authenticate(c)

        # Streams the request body in small chunks.
        def chunks():
            yield b'{"title": "t", "text": "'
            yield b"x" * 200
            yield b'"}'

        resp = c.post(
            "/api/analyses", content=chunks(), headers={"Content-Type": "application/json"}
        )
    assert_envelope(resp, 413, "PAYLOAD_TOO_LARGE", False)


# Checks each mock error trigger maps to the right status and code.
@pytest.mark.parametrize(
    ("token", "status", "code", "retryable"),
    [
        ("malformed", 502, "MALFORMED_AI_RESPONSE", True),
        ("invalid_schema", 502, "MALFORMED_AI_RESPONSE", True),
        ("ratelimit", 429, "RATE_LIMITED", True),
        ("timeout", 504, "PROVIDER_TIMEOUT", True),
        ("unavailable", 503, "PROVIDER_UNAVAILABLE", True),
        ("auth", 502, "PROVIDER_AUTH_ERROR", False),
        ("context", 422, "CONTEXT_TOO_LONG", False),
    ],
)
def test_mock_error_triggers(
    client: TestClient, token: str, status: int, code: str, retryable: bool
) -> None:
    resp = post(client, text=f"Some notes [[mock:{token}]]")
    assert_envelope(resp, status, code, retryable)
    if status == 429:
        assert resp.headers["retry-after"] == "2"
    assert client.get("/api/analyses").json()["total"] == 0


# Checks mock triggers that should still produce a saved analysis.
@pytest.mark.parametrize("token", ["fenced", "malformed_once"])
def test_mock_success_triggers(client: TestClient, token: str) -> None:
    assert post(client, text=f"notes [[mock:{token}]]").status_code == 201


# Checks retries go through the injected sleep instead of real waits.
def test_retries_use_injected_sleep(client: TestClient, sleep: RecordingSleep) -> None:
    post(client, text="x [[mock:timeout]]")
    assert len(sleep.delays) == 2


# Checks the list is newest first and supports limit and offset.
def test_list_newest_first_and_pagination(client: TestClient) -> None:
    ids = [post(client, title=f"Doc {i}").json()["id"] for i in range(3)]
    body = client.get("/api/analyses").json()
    assert body["total"] == 3
    assert [i["id"] for i in body["items"]] == ids[::-1]
    assert body["limit"] == 20 and body["offset"] == 0
    item = body["items"][0]
    assert set(item) == {"id", "title", "created_at", "summary_preview", "action_item_count"}
    page = client.get("/api/analyses?limit=1&offset=1").json()
    assert [i["id"] for i in page["items"]] == [ids[1]]


# Checks invalid list query parameters return VALIDATION_ERROR.
@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "limit=abc"])
def test_list_bad_query(client: TestClient, query: str) -> None:
    assert_envelope(client.get(f"/api/analyses?{query}"), 422, "VALIDATION_ERROR", False)


# Checks an analysis can be fetched and then deleted.
def test_get_and_delete(client: TestClient) -> None:
    created = post(client).json()
    got = client.get(f"/api/analyses/{created['id']}")
    assert got.status_code == 200
    assert got.json() == created
    assert client.delete(f"/api/analyses/{created['id']}").status_code == 204
    assert_envelope(client.get(f"/api/analyses/{created['id']}"), 404, "NOT_FOUND", False)
    assert_envelope(client.delete(f"/api/analyses/{created['id']}"), 404, "NOT_FOUND", False)


# Checks unknown or malformed IDs return NOT_FOUND.
@pytest.mark.parametrize("bad_id", [str(uuid.uuid4()), "not-a-uuid", "1' OR '1'='1"])
def test_unknown_or_malformed_id(client: TestClient, bad_id: str) -> None:
    assert_envelope(client.get(f"/api/analyses/{bad_id}"), 404, "NOT_FOUND", False)


# Checks unknown routes and methods return JSON 404 and 405 errors.
def test_unknown_route_and_method(client: TestClient) -> None:
    assert_envelope(client.get("/api/nope"), 404, "NOT_FOUND", False)
    assert_envelope(client.put("/api/analyses"), 405, "METHOD_NOT_ALLOWED", False)


# Checks saved analyses survive restarting the app.
def test_history_persists_across_app_instances(settings: Settings) -> None:
    with TestClient(create_app(settings)) as c1:
        authenticate(c1)
        created = post(c1).json()
    with TestClient(create_app(settings)) as c2:
        c2.headers["Authorization"] = c1.headers["Authorization"]
        assert c2.get(f"/api/analyses/{created['id']}").json()["id"] == created["id"]
        assert c2.get("/api/analyses").json()["total"] == 1


# Checks an unexpected crash returns a generic 500 without leaking details.
def test_unexpected_exception_returns_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import analysis_service

    # Raises an unexpected error to simulate a crash.
    def boom(*_a, **_k):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(analysis_service.AnalysisService, "analyze", boom)
    resp = post(client)
    err = assert_envelope(resp, 500, "INTERNAL_ERROR", False)
    assert "secret internal detail" not in resp.text
    assert err["message"] == "Something went wrong on our side."


# Checks the health endpoint reports ok in mock mode.
def test_health(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["mock_mode"] is True
    assert body["database"] == "ok"
    assert body["provider"] == "mock"
    assert body["prompt_version"] == "analysis-v2"


# Checks health reports degraded when the database fails.
def test_health_degraded_when_db_fails(client: TestClient, monkeypatch) -> None:
    import sqlite3

    from app.api import routes_health

    # Raises a database error to simulate a broken connection.
    def broken(_path: str):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(routes_health, "connect", broken)
    body = client.get("/api/health").json()
    assert body["status"] == "degraded"
    assert body["database"] == "error"


# Checks CORS preflight allows the configured origin.
def test_cors_headers(client: TestClient) -> None:
    resp = client.options(
        "/api/analyses",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"
    resp = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert "x-request-id" in resp.headers["access-control-expose-headers"].lower()


# Checks the OpenAPI spec and docs page are served.
def test_openapi_and_docs(client: TestClient) -> None:
    spec = client.get("/api/openapi.json").json()
    assert "ErrorResponse" in spec["components"]["schemas"]
    assert "/api/analyses/{analysis_id}" in spec["paths"]
    assert client.get("/api/docs").status_code == 200


# Checks document text never appears in the logs.
def test_document_text_never_logged(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    secret_text = "meeting about ZEBRA-CONFIDENTIAL-PROJECT"
    post(client, text=secret_text)
    assert "ZEBRA-CONFIDENTIAL-PROJECT" not in caplog.text


# Checks a custom provider passed to create_app is used.
def test_custom_provider_injection(settings: Settings) -> None:
    provider = FakeProvider(
        [valid_json(), '{"contradictions": [], "risks": [], "dependencies": []}']
    )
    app = create_app(settings, provider=provider)
    app.state.sleep = RecordingSleep()
    with TestClient(app) as c:
        authenticate(c)
        body = post(c).json()
    assert body["provider"] == "fake"
    assert len(provider.calls) == 2


MEETING_TEXT = (
    "Weekly sync transcript. Attendees: Priya, Marco, Lena.\n"
    "Priya: The billing page redesign is our top priority; I'll draft the pricing copy by Friday.\n"
    "Marco: The CSV export still times out for big accounts. It's a blocker, I'll take it.\n"
    "Lena: We haven't decided whether to delay push notifications. Budget for QA is unconfirmed.\n"
    "Testing depends on API readiness."
)


# Checks the mock produces every new section with verified evidence for the sample meeting.
def test_mock_full_analysis_sections(client: TestClient) -> None:
    result = post(client, text=MEETING_TEXT).json()["result"]
    assert result["intelligence"]["status"] == "complete"
    assert [p["text"] for p in result["entities"]["people"]] == ["Priya", "Marco", "Lena"]
    owners = [a["owner"] for a in result["action_items"]]
    assert owners[:2] == ["Priya", "Marco"]
    assert result["action_items"][0]["evidence_status"] == "verified"
    assert {d["status"] for d in result["decisions"]} == {"confirmed", "pending"}
    assert result["dependencies"][0]["dependent_task"] == "Testing"
    assert any(r["origin"] == "explicit" for r in result["risks"])
    categories = {q["category"] for q in result["open_question_details"]}
    assert {"missing_owner", "missing_deadline"} <= categories
    assert result["open_questions"] == [q["question"] for q in result["open_question_details"]]


# Checks owners the mock invents for unrelated text are removed by validation.
def test_mock_owners_not_in_text_are_removed(client: TestClient) -> None:
    result = post(client, text="Meeting notes. We talked about the roadmap.").json()["result"]
    assert all(a["owner"] is None for a in result["action_items"])
    assert result["validation"]["checks"]["owners_removed"] >= 1


# Checks an intelligence failure still returns 201, and a re-run reports it again.
def test_intelligence_failure_and_rerun(client: TestClient) -> None:
    created = post(client, text="Meeting notes [[mock:intel_malformed]]").json()
    assert created["result"]["intelligence"]["status"] == "failed"
    rerun = client.post(f"/api/analyses/{created['id']}/intelligence")
    assert_envelope(rerun, 502, "MALFORMED_AI_RESPONSE", True)


# Checks a rate-limited re-run returns the standard error envelope.
def test_rerun_rate_limited(client: TestClient) -> None:
    created = post(client, text="Meeting notes [[mock:intel_ratelimit]]").json()
    assert created["result"]["intelligence"]["status"] == "failed"
    resp = client.post(f"/api/analyses/{created['id']}/intelligence")
    assert_envelope(resp, 429, "RATE_LIMITED", True)


# Checks the re-run endpoint succeeds for a normal analysis and 404s for unknown IDs.
def test_rerun_endpoint(client: TestClient) -> None:
    created = post(client, text=MEETING_TEXT).json()
    resp = client.post(f"/api/analyses/{created['id']}/intelligence")
    assert resp.status_code == 200
    assert resp.json()["result"]["intelligence"]["documents_compared"] == 0
    assert client.get(f"/api/analyses/{created['id']}").json() == resp.json()
    missing = client.post(f"/api/analyses/{uuid.uuid4()}/intelligence")
    assert_envelope(missing, 404, "NOT_FOUND", False)


# Checks the mock conflict trigger produces a within-document contradiction.
def test_mock_conflict_trigger(client: TestClient) -> None:
    text = "Launch is on December 15. Launch is on December 20. [[mock:conflict]]"
    conflicts = post(client, text=text).json()["result"]["contradictions"]
    assert conflicts[0]["scope"] == "within_document"
    assert [v["evidence_status"] for v in conflicts[0]["values"]] == ["verified", "verified"]
