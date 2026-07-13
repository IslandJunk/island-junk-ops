"""QuickBooks Online — READ-ONLY sync (WS4).

GUARDRAIL: the app NEVER creates, edits, or sends an invoice. It only READS QBO to detect two
transitions on invoices the owner sends BY HAND — invoice-sent (start the 48h clock + reminder)
and payment (clear the reminder, mark paid). Matching is by the `BIN-xxxx` reference code the
owner pastes into the invoice's PO/reference field. Every call here is a GET or a token grant;
there is no POST to any /invoice or /payment resource, by design.

OAuth2 (authorization-code). Secrets live in `.env` (git-ignored) → absent means dry-run (this
module makes no network calls). Sandbox for the build; production creds go in the Render
dashboard later. Uses httpx directly (already a dep) — no Intuit SDK, to stay light on 3.14.

Hosts (authorize + token are the SAME for sandbox and production; only the data host differs):
  authorize      https://appcenter.intuit.com/connect/oauth2
  token          https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer
  data sandbox   https://sandbox-quickbooks.api.intuit.com
  data prod      https://quickbooks.api.intuit.com
"""
from __future__ import annotations

import base64
import secrets as _secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from app.core.config import settings

# Read-only scope. `com.intuit.quickbooks.accounting` is the narrowest scope that still exposes
# Invoice + Payment reads; read-only is enforced by this module only ever issuing GETs.
SCOPE = "com.intuit.quickbooks.accounting"
_AUTHORIZE_URL = "https://appcenter.intuit.com/connect/oauth2"
_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
_MINOR_VERSION = "70"  # QBO API minor version pin


class QBOError(RuntimeError):
    """A QuickBooks API / OAuth error surfaced to the caller (bad code, expired token, 4xx)."""


def is_configured() -> bool:
    """OAuth app credentials present. A LIVE connection additionally needs a stored token."""
    return settings.is_qbo_configured


def _data_base() -> str:
    return ("https://quickbooks.api.intuit.com"
            if settings.qbo_environment == "production"
            else "https://sandbox-quickbooks.api.intuit.com")


# ── OAuth: authorize → callback → token ───────────────────────────────────────

def make_state() -> str:
    """Opaque CSRF state to round-trip through the redirect and verify on callback."""
    return _secrets.token_urlsafe(24)


def authorize_url(state: str) -> str:
    """The Intuit consent URL to redirect the owner to. `redirect_uri` MUST exactly match one
    registered on the Intuit app (localhost for local test — NOT 127.0.0.1)."""
    q = urlencode({
        "client_id": settings.qbo_client_id,
        "response_type": "code",
        "scope": SCOPE,
        "redirect_uri": settings.qbo_redirect_uri,
        "state": state,
    })
    return f"{_AUTHORIZE_URL}?{q}"


def _basic_auth() -> str:
    raw = f"{settings.qbo_client_id}:{settings.qbo_client_secret}".encode()
    return base64.b64encode(raw).decode()


def _token_request(data: dict) -> dict:
    import httpx
    resp = httpx.post(
        _TOKEN_URL,
        headers={
            "Authorization": f"Basic {_basic_auth()}",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=data, timeout=30,
    )
    if resp.status_code >= 400:
        raise QBOError(f"QBO token {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def _normalize_token(tok: dict) -> dict:
    """Intuit's token payload → our stored shape, expiries as tz-aware datetimes. Access token
    lives ~1h; refresh token ~100 days (and rotates — always persist the NEW refresh token)."""
    now = datetime.now(timezone.utc)
    return {
        "access_token": tok.get("access_token"),
        "refresh_token": tok.get("refresh_token"),
        "access_expires_at": now + timedelta(seconds=int(tok.get("expires_in", 3600))),
        "refresh_expires_at": now + timedelta(seconds=int(tok.get("x_refresh_token_expires_in", 8_640_000))),
    }


def exchange_code(code: str) -> dict:
    """Exchange an authorization code (from the callback) for tokens. Returns the normalized
    token dict; the caller stores it + the realmId (company id, also from the callback)."""
    return _normalize_token(_token_request({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.qbo_redirect_uri,
    }))


def refresh(refresh_token: str) -> dict:
    """Refresh an expired access token. Returns the normalized token dict (NEW refresh token
    included — Intuit rotates it, so the caller must persist the returned refresh_token)."""
    return _normalize_token(_token_request({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }))


# ── Read-only data access (GET only) ──────────────────────────────────────────

def _get(realm_id: str, access_token: str, path: str, params: dict | None = None) -> dict:
    import httpx
    p = {"minorversion": _MINOR_VERSION}
    if params:
        p.update(params)
    resp = httpx.get(
        f"{_data_base()}/v3/company/{realm_id}{path}",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        params=p, timeout=30,
    )
    if resp.status_code == 401:
        raise QBOError("QBO 401: access token expired or revoked (refresh needed)")
    if resp.status_code >= 400:
        raise QBOError(f"QBO GET {path} {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def query(realm_id: str, access_token: str, sql: str) -> dict:
    """Run a read-only QBO query ('SELECT ... FROM Invoice ...'). Returns the QueryResponse
    dict (e.g. {'Invoice': [...], 'maxResults': n}). Read-only — there is no mutating counterpart."""
    return _get(realm_id, access_token, "/query", {"query": sql}).get("QueryResponse", {})


def company_info(realm_id: str, access_token: str) -> dict:
    """Fetch CompanyInfo — used right after Connect to confirm the link and show the company
    name back to the owner. Proof the token + realm work."""
    return _get(realm_id, access_token, f"/companyinfo/{realm_id}").get("CompanyInfo", {})
