"""Twilio SMS client — the app's ONLY texter, and it sends ONLY from the shared updates
line (SMS spec §1–2, never-list §2.6). The manager's two-way MAIN lines are hard-coded as
forbidden senders; every send asserts the from-number is exactly the configured updates
line before doing anything. Mirrors the calendar guard's shape.

Creds live in `.env` (git-ignored). Until they're set the client runs in **dry-run**: it
composes + returns a marker but never calls Twilio, so all the flows work in development.
"""
from __future__ import annotations

from app.core.config import settings


class SmsGuardError(RuntimeError):
    pass


def _forbidden_senders() -> set[str]:
    """The manager's real MAIN lines — the app must NEVER send from these (§2.6)."""
    return {settings.victoria_main_line, settings.nanaimo_main_line}


def _assert_updates_line(from_number: str | None) -> str:
    if not from_number:
        raise SmsGuardError("No updates line configured (twilio_updates_line).")
    if from_number in _forbidden_senders():
        raise SmsGuardError(f"REFUSING: '{from_number}' is a manager MAIN line — never send from it.")
    if from_number != settings.twilio_updates_line:
        raise SmsGuardError("REFUSING: sender is not the configured updates line.")
    return from_number


_client = None


def _twilio():
    global _client
    if _client is None:
        from twilio.rest import Client  # lazy — only needed to actually send
        _client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    return _client


def send_raw(*, to: str, body: str, media_url: str | None = None) -> dict:
    """Send one SMS/MMS from the updates line. Returns {sent, sid, dry_run}. In dry-run
    (creds absent) it does NOT call Twilio — it returns sent=False, dry_run=True so callers
    can still log the composed message. The from-line guard runs in BOTH modes."""
    from_number = _assert_updates_line(settings.twilio_updates_line)
    if not settings.is_sms_configured:
        return {"sent": False, "sid": None, "dry_run": True}
    kwargs = {"to": to, "from_": from_number, "body": body}
    if media_url:
        kwargs["media_url"] = [media_url]
    msg = _twilio().messages.create(**kwargs)
    return {"sent": True, "sid": msg.sid, "dry_run": False}
