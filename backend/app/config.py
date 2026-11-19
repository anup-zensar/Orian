"""Application configuration (spec §5.3).

Values come from environment variables or ``backend/.env`` (see ``.env.example``).
Every external system and AI capability is selected here (spec §10, NFR-01).
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,  # "SEED_DATE=" in .env means "not set"
        extra="ignore",
    )

    # --- spec §5.3 ---
    demo_mode: bool = True  # shows Demo controls, enables /admin/demo endpoints
    ai_mode: Literal["mock", "live"] = "mock"  # (live = optional Azure OpenAI, free-text chat only)
    mail_mode: Literal["mock", "graph"] = "mock"  # (graph = stub)
    orion_mailbox: str = "orion-noreply@example.com"
    reminder_job_enabled: bool = False  # true = APScheduler runs the reminder engine every 15 min
    seed_date: date | None = None  # optional fixed "today" for deterministic demos
    database_url: str = "sqlite:///./orion.db"  # relative SQLite paths resolve against backend/
    azure_openai_endpoint: str = ""
    azure_openai_key: str = ""
    azure_openai_deployment: str = ""

    # --- additions (documented in PLAN.md) ---
    seed_dir: Path = REPO_DIR / "seed"  # A-04: seed files are read in place
    storage_dir: Path = BACKEND_DIR / "app" / "storage"  # uploaded files, generated PPT/XLSX
    mock_delay_ms: int = 600  # A-18: simulated latency of mock services (0 in tests)
    app_base_url: str = "http://localhost:5173"  # used for deep links in emails / cards
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    max_upload_mb: int = 25  # A-24: upload size limit
    # CR-01 design 3: a database whose schema version differs from the code is dropped, re-created
    # and re-seeded at startup (demo data is synthetic). false = refuse to start with a clear error.
    schema_auto_reset: bool = True

    @field_validator("ai_mode", "mail_mode", mode="before")
    @classmethod
    def _normalise_mode(cls, value: object) -> object:
        """Case/whitespace tolerant; a typo still fails at startup via the Literal type."""
        return value.strip().lower() if isinstance(value, str) else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
