"""Transactional email via SendGrid — used for owner-2FA codes (a recovery channel
alongside SMS). Mirrors the other integrations: lazy `httpx`, creds-gated, and it NEVER
pretends to have sent. Absent creds → EmailNotConfigured so the caller can tell the owner
"email isn't set up yet" instead of silently dropping a security code.

SendGrid v3 send API: POST https://api.sendgrid.com/v3/mail/send, Bearer key, 202 = queued.
The from-email must be a SendGrid-verified single sender (see settings.sendgrid_from_email).
"""
from __future__ import annotations

from app.core.config import settings

SENDGRID_SEND_URL = "https://api.sendgrid.com/v3/mail/send"


class EmailError(RuntimeError):
    """SendGrid returned an error (non-2xx) or the request failed."""


class EmailNotConfigured(EmailError):
    """No SendGrid key / verified sender — the email channel is unavailable."""


def send_email(to: str, subject: str, text: str) -> None:
    """Send a plain-text email via SendGrid. Raises EmailNotConfigured when creds are
    absent, EmailError on a delivery failure. Returns None on success (202 Accepted)."""
    if not settings.is_email_configured:
        raise EmailNotConfigured("SendGrid is not configured (missing key or verified sender)")

    import httpx

    payload = {
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": settings.sendgrid_from_email, "name": settings.sendgrid_from_name},
        "subject": subject,
        "content": [{"type": "text/plain", "value": text}],
    }
    try:
        resp = httpx.post(
            SENDGRID_SEND_URL,
            headers={
                "Authorization": f"Bearer {settings.sendgrid_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
    except Exception as exc:  # network / DNS / timeout
        raise EmailError(f"SendGrid request failed: {exc}") from exc

    # SendGrid returns 202 Accepted on success; anything >= 300 is an error.
    if resp.status_code >= 300:
        raise EmailError(f"SendGrid {resp.status_code}: {resp.text[:300]}")
