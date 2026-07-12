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

    # ── Twilio SMS (island-junk-SPEC-sms-and-texting.md) ──────────────────────
    # Secrets live in .env (git-ignored); absent until Wes provides them → the app
    # runs in dry-run (composes + logs, never sends). Canadian local number, no A2P 10DLC.
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    # The ONE shared, send-only updates line the app texts from (both brands). E.164.
    twilio_updates_line: str | None = "+17789065865"   # 778-906-5865
    # The manager's real two-way MAIN lines — the app NEVER sends from these; used only as
    # the numbers the reply auto-router points recognised customers back to.
    victoria_main_line: str = "+17789665865"           # 778-966-5865
    nanaimo_main_line: str = "+17789775865"            # 778-977-5865
    # Where the app FORWARDS an inbound customer reply (with who-it-is + job context) so the
    # manager isn't left guessing. Defaults to the brand's main line (the manager's phone);
    # override in .env to send nudges to a different phone/number. Set blank to disable.
    manager_notify_victoria: str | None = None
    manager_notify_nanaimo: str | None = None
    # Verify inbound Twilio webhook signatures when set (the request URL's public base).
    twilio_validate_signatures: bool = False

    # ── Square (payment LINKS only — the app never charges a card, §2/§3) ─────
    # Secrets in .env; absent → dry-run (returns a placeholder link, calls nothing).
    square_access_token: str | None = None
    square_location_id: str | None = None
    square_environment: str = "sandbox"      # "sandbox" | "production"
    # Public Web Payments SDK application id (WS3 card-on-file capture at bin booking). Not a
    # secret; the SDK card field needs it + the location id. Sandbox id for the build.
    square_application_id: str | None = None

    # ── Dropbox (auto-file job photos; TEST folder first, §4/§10) ─────────────
    dropbox_access_token: str | None = None      # or a refresh-token flow later
    dropbox_root: str = "/Island Junk TEST"      # never the live photo tree until go-live

    @property
    def is_db_configured(self) -> bool:
        return bool(self.database_url)

    @property
    def is_sms_configured(self) -> bool:
        """True only when the app can actually SEND (account creds + the updates line)."""
        return bool(self.twilio_account_sid and self.twilio_auth_token and self.twilio_updates_line)

    @property
    def is_square_configured(self) -> bool:
        return bool(self.square_access_token and self.square_location_id)

    @property
    def is_dropbox_configured(self) -> bool:
        return bool(self.dropbox_access_token)


settings = Settings()
