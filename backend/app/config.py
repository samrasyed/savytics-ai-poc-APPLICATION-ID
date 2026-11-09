from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigurationError(RuntimeError):
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    APP_ENV: Literal["development", "test", "production"] = "development"

    LLM_PROVIDER: Literal["mock", "openai_compatible"] = "mock"
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    LLM_API_KEY: SecretStr = Field(default=SecretStr(""), repr=False)
    LLM_MODEL: str = ""
    LLM_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0)
    LLM_TEMPERATURE: float = Field(default=0.2, ge=0, le=2)
    LLM_MAX_OUTPUT_TOKENS: int = Field(default=8192, gt=0)
    LLM_JSON_MODE: bool = True
    LLM_MAX_TRANSIENT_RETRIES: int = Field(default=2, ge=0, le=10)
    LLM_MAX_REPAIR_ATTEMPTS: int = Field(default=1, ge=0, le=5)
    LLM_TOTAL_BUDGET_SECONDS: float = Field(default=90.0, gt=0)
    LLM_MAX_RETRY_AFTER_SECONDS: float = Field(default=10.0, ge=0, le=120)
    LLM_REASONING_EFFORT: Literal["", "low", "medium", "high"] = ""
    LLM_ENABLE_INTELLIGENCE: bool = True
    CROSS_DOC_CONTEXT_LIMIT: int = Field(default=5, ge=0, le=20)

    MAX_TITLE_CHARS: int = Field(default=200, gt=0)
    MAX_INPUT_CHARS: int = Field(default=50_000, gt=0)
    MAX_BODY_BYTES: int = Field(default=262_144, gt=0)

    DATABASE_PATH: str = "/tmp/analyses.db" if os.environ.get("VERCEL") else "./data/analyses.db"
    DATABASE_URL: SecretStr = Field(
        default=SecretStr(""),
        repr=False,
        validation_alias=AliasChoices("DATABASE_URL", "POSTGRES_URL"),
    )
    SESSION_DAYS: int = Field(default=30, gt=0, le=365)
    CORS_ORIGINS: str = "http://localhost:5173"
    MOCK_LATENCY_MS: int = Field(default=300, ge=0)
    LOG_LEVEL: str = "INFO"

    # Normalizes the log level to uppercase and falls back to INFO when blank.
    @field_validator("LOG_LEVEL")
    @classmethod
    def _upper_log_level(cls, value: str) -> str:
        return value.strip().upper() or "INFO"

    # Splits the comma-separated CORS_ORIGINS value into a clean list.
    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # Returns the Postgres URL when one is set, otherwise the SQLite file path.
    @property
    def database_target(self) -> str:
        return self.DATABASE_URL.get_secret_value().strip() or self.DATABASE_PATH

    # Tells whether the app is running with the mock provider.
    @property
    def is_mock(self) -> bool:
        return self.LLM_PROVIDER == "mock"

    # Returns the model name actually in use for the current provider.
    @property
    def effective_model(self) -> str:
        if self.is_mock:
            return "mock-analyzer-v1"
        return self.LLM_MODEL

    # Fails fast if a real provider is selected without its required settings.
    def validate_for_startup(self) -> None:
        if self.LLM_PROVIDER == "openai_compatible":
            missing = []
            if not self.LLM_API_KEY.get_secret_value().strip():
                missing.append("LLM_API_KEY")
            if not self.LLM_MODEL.strip():
                missing.append("LLM_MODEL")
            if not self.LLM_BASE_URL.strip():
                missing.append("LLM_BASE_URL")
            if missing:
                raise ConfigurationError(
                    "LLM_PROVIDER=openai_compatible requires these environment variables: "
                    + ", ".join(missing)
                )


# Loads the settings once and reuses the same instance afterwards.
@lru_cache
def get_settings() -> Settings:
    return Settings()
