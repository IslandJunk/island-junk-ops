"""Dropbox OAuth2 — durable connect for per-job photo folders (§4/§10).

The owner connects once; we store a short-lived access token (~4h) + a long-lived refresh token
(Dropbox refresh tokens do NOT expire or rotate). `get_valid_access_token` refreshes on demand so
uploads never hit an expired token. App key/secret in .env / Render -> absent means dry-run.

Hosts:
  authorize  https://www.dropbox.com/oauth2/authorize
  token      https://api.dropboxapi.com/oauth2/token
  account    https://api.dropboxapi.com/2/users/get_current_account
"""
from __future__ import annotations

import base64
import secrets as _secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from app.core.config import settings

# account_info.read: confirm the account on connect. files.*: upload/read job photos.
# sharing.write: create the shared folder link that rides into the calendar event at booking.
SCOPE = "account_info.read files.metadata.read files.content.write files.content.read sharing.write"
_AUTHORIZE_URL = "https://www.dropbox.com/oauth2/authorize"
_TOKEN_URL = "https://api.dropboxapi.com/oauth2/token"
_ACCOUNT_URL = "https://api.dropboxapi.com/2/users/get_current_account"


class DropboxAuthError(RuntimeError):
    """A Dropbox OAuth error surfaced to the caller (bad code, expired/revoked token, 4xx)."""


def is_configured() -> bool:
    """OAuth app credentials present. A LIVE connection additionally needs a stored token."""
    return settings.is_dropbox_oauth_configured


def make_state() -> str:
    return _secrets.token_urlsafe(24)


def authorize_url(state: str) -> str:
    """The Dropbox consent URL. redirect_uri MUST exactly match one registered on the app."""
    q = urlencode({
        "client_id": settings.dropbox_app_key,
        "response_type": "code",
        "redirect_uri": settings.dropbox_redirect_uri,
        "state": state,
        "token_access_type": "offline",   # -> returns a durable refresh token
        "scope": SCOPE,
    })
    return f"{_AUTHORIZE_URL}?{q}"


def _basic_auth() -> str:
    raw = f"{settings.dropbox_app_key}:{settings.dropbox_app_secret}".encode()
    return base64.b64encode(raw).decode()


def _token_request(data: dict) -> dict:
    import httpx
    resp = httpx.post(
        _TOKEN_URL,
        headers={"Authorization": f"Basic {_basic_auth()}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data=data, timeout=30,
    )
    if resp.status_code >= 400:
        raise DropboxAuthError(f"Dropbox token {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def exchange_code(code: str) -> dict:
    """Exchange the callback code for {access_token, refresh_token, access_expires_at}."""
    tok = _token_request({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.dropbox_redirect_uri,
    })
    now = datetime.now(timezone.utc)
    return {
        "access_token": tok.get("access_token"),
        "refresh_token": tok.get("refresh_token"),
        "access_expires_at": now + timedelta(seconds=int(tok.get("expires_in", 14400))),
    }


def refresh(refresh_token: str) -> dict:
    """Refresh the short-lived access token. Dropbox does NOT return a new refresh token."""
    tok = _token_request({"grant_type": "refresh_token", "refresh_token": refresh_token})
    now = datetime.now(timezone.utc)
    return {
        "access_token": tok.get("access_token"),
        "access_expires_at": now + timedelta(seconds=int(tok.get("expires_in", 14400))),
    }


def get_current_account(access_token: str) -> dict:
    """Confirm the connection + return the account (shown back to the owner). No-arg RPC: JSON
    null body."""
    import httpx
    resp = httpx.post(
        _ACCOUNT_URL,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        content="null", timeout=30,
    )
    if resp.status_code >= 400:
        raise DropboxAuthError(f"Dropbox account {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def get_valid_access_token(db) -> str | None:
    """Return a currently-valid Dropbox access token for the active connection, refreshing it via
    the stored refresh token when it's within 60s of expiry. None when not connected."""
    from sqlalchemy import select

    from app.models.dropbox import DropboxConnection
    conn = db.scalar(select(DropboxConnection).where(DropboxConnection.active.is_(True)))
    if conn is None or not conn.refresh_token:
        return None
    now = datetime.now(timezone.utc)
    exp = conn.access_expires_at
    if exp is not None and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if conn.access_token and exp is not None and exp > now + timedelta(seconds=60):
        return conn.access_token
    t = refresh(conn.refresh_token)
    conn.access_token = t["access_token"]
    conn.access_expires_at = t["access_expires_at"]
    db.commit()
    return conn.access_token
