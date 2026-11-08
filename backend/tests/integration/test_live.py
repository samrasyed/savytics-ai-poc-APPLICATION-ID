from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

pytestmark = pytest.mark.live

TRANSCRIPT = """Weekly sync transcript. Attendees: Priya, Marco, Lena.
Priya: The billing page redesign is our top priority; I'll draft the pricing copy by Friday.
Marco: The CSV export still times out for big accounts. It's a blocker, I'll take it.
Lena: We haven't decided whether to delay push notifications. Budget for QA is unconfirmed."""


# Runs a real analysis against a live provider when enabled by env vars.
@pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1" or not os.getenv("LLM_API_KEY"),
    reason="set RUN_LIVE_TESTS=1 and LLM_API_KEY to run live tests",
)
def test_live_analysis(tmp_path) -> None:
    settings = Settings(
        LLM_PROVIDER="openai_compatible",
        DATABASE_PATH=str(tmp_path / "live.db"),
    )
    with TestClient(create_app(settings)) as client:
        resp = client.post("/api/analyses", json={"title": "Weekly sync", "text": TRANSCRIPT})
    assert resp.status_code == 201, resp.text
    result = resp.json()["result"]
    assert result["summary"]
    assert result["action_items"]
