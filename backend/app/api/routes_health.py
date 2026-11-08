from __future__ import annotations

import logging
import sqlite3

from fastapi import APIRouter

from app import __version__
from app.api.dependencies import ProviderDep, SettingsDep
from app.db.database import connect
from app.domain.schemas import HealthResponse
from app.prompts.analysis_prompt import PROMPT_VERSION

router = APIRouter(prefix="/api", tags=["health"])
logger = logging.getLogger(__name__)


# Reports service status, the active provider and whether the database is reachable.
@router.get("/health", response_model=HealthResponse, summary="Service health")
def health(settings: SettingsDep, provider: ProviderDep) -> HealthResponse:
    db_ok = True
    try:
        conn = connect(settings.DATABASE_PATH)
        try:
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        logger.error("health check database error=%s", type(exc).__name__)
        db_ok = False
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        provider=provider.name,
        model=provider.model,
        mock_mode=provider.name == "mock",
        prompt_version=PROMPT_VERSION,
        database="ok" if db_ok else "error",
        version=__version__,
    )
