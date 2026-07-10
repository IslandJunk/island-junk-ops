"""App settings, loaded from environment / .env."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Island Junk Ops"
    environment: str = "development"

    # SQLAlchemy URL, e.g. postgresql+psycopg://user:pass@host:5432/db
    # Optional so the app boots (e.g. /health) before a DB is attached.
    database_url: str | None = None

    # Signs session cookies. MUST be overridden anywhere shared/deployed.
    session_secret: str = "dev-insecure-change-me"

    # Google Calendar (booking writes ONLY here — never a live calendar).
    google_service_account_file: str = "spike/service-account-key.json"
    google_test_calendar_id: str | None = (
        "c_37fdece0f833b792c645b6d195f07c865611cd9de35a2a142620b768e6324f34@group.calendar.google.com"
    )
    # Off-board CC-charge reminder calendar (§9/§11) — the ONLY other calendar the app
    # may write to; reminders appear here and turn purple/deleted when paid (Wes 2026-07).
    google_reminder_calendar_id: str | None = (
        "c_139129e65b40062ead44d4aa680aa8c186c997fdcc9f8c8946a2fc6347f0b83c@group.calendar.google.com"
    )
    # Off-board punch-time calendar (TEST) — mirrors crew clock in/out as one event per
    # person per day so the office can see hours at a glance. Shared with the service
    # account 2026-07 ("PUNCH TIME - TEST"). Never a dispatch/live calendar.
    google_punch_calendar_id: str | None = (
        "c_1033bcf8590acc0d57229b30e59d0169c4211883dd51ad18acb15476cc0193aa@group.calendar.google.com"
    )

    @property
    def is_db_configured(self) -> bool:
        return bool(self.database_url)


settings = Settings()
