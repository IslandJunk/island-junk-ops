"""Dropbox — Connect + status (OWNER-ONLY).

The owner links Wes's Dropbox account so the app can auto-file per-job photos (§4/§10) and drop a
per-job folder link into the booking's calendar event. OAuth2 (authorization-code, offline) —
/connect + /callback do the handshake and store an encrypted access + refresh token. One account
(not per-brand); the brand is expressed by the folder path.

CSRF: the OAuth `state` is a time-boxed signed token bound to the initiating owner's employee id.
The `ij_session` cookie is SameSite=Lax, so it survives the top-level redirect back from Dropbox.
"""
from __future__ import annotations

import html

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_employee, require_owner_2fa
from app.auth.guards import is_owner
from app.core.config import settings
from app.db.session import get_db
from app.integrations import dropbox_oauth
from app.models.dropbox import DropboxConnection
from app.models.employee import Employee

router = APIRouter(prefix="/dropbox", tags=["dropbox"])

_state_serializer = URLSafeTimedSerializer(settings.session_secret, salt="ij-dropbox-oauth")
_STATE_MAX_AGE = 900   # 15 min to complete the Dropbox consent round-trip


def _require_owner(emp: Employee) -> None:
    if not is_owner(emp):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Owner only")


def _active_connection(db: DbSession) -> DropboxConnection | None:
    return db.scalar(select(DropboxConnection).where(DropboxConnection.active.is_(True)))


def _done_page(message: str, ok: bool) -> HTMLResponse:
    """Confirmation page after the OAuth round-trip, with a link back to the Owner Hub. ASCII only
    (served-page surrogate gotcha, PROGRESS.md §5)."""
    colour = "#3CA03C" if ok else "#C0392B"
    title = "Dropbox connected" if ok else "Dropbox not connected"
    msg = html.escape(message)
    return HTMLResponse(
        "<!doctype html><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<div style=\"font-family:Inter,system-ui,sans-serif;max-width:520px;margin:14vh auto;"
        "padding:0 20px;text-align:center;color:#141414\">"
        f"<div style=\"font-size:44px;line-height:1;color:{colour}\">{'OK' if ok else '!'}</div>"
        f"<h1 style=\"font-size:22px;margin:14px 0 6px\">{title}</h1>"
        f"<p style=\"color:#555;font-size:15px\">{msg}</p>"
        "<a href='/app/owner-hub' style=\"display:inline-block;margin-top:18px;background:#F05014;"
        "color:#fff;text-decoration:none;font-weight:700;padding:12px 20px;border-radius:10px\">"
        "Back to Owner Hub</a></div>",
        status_code=200 if ok else 400,
    )


@router.get("/connect")
def connect(request: Request, emp: Employee = Depends(get_current_employee)) -> Response:
    """Owner taps 'Connect Dropbox' -> redirect to Dropbox consent. State is signed to this owner."""
    require_owner_2fa(request, emp)
    if not dropbox_oauth.is_configured():
        return _done_page("Dropbox isn't configured yet (missing app key/secret).", ok=False)
    state = _state_serializer.dumps({"eid": str(emp.id)})
    return RedirectResponse(dropbox_oauth.authorize_url(state), status_code=302)


@router.get("/callback")
def callback(request: Request, code: str | None = None, state: str | None = None,
             error: str | None = None, db: DbSession = Depends(get_db),
             emp: Employee = Depends(get_current_employee)) -> Response:
    """Dropbox redirects here with an auth code. Verify state, exchange for tokens, confirm the
    account, and store the connection."""
    _require_owner(emp)
    if error:
        return _done_page(f"Dropbox consent was cancelled ({error}).", ok=False)
    if not (code and state):
        return _done_page("Dropbox didn't return the expected code/state.", ok=False)
    try:
        data = _state_serializer.loads(state, max_age=_STATE_MAX_AGE)
    except SignatureExpired:
        return _done_page("The connect link expired - tap Connect Dropbox again.", ok=False)
    except BadSignature:
        return _done_page("The connect link was invalid - please try again.", ok=False)
    if data.get("eid") != str(emp.id):
        return _done_page("That connect link was started by a different account.", ok=False)

    try:
        tok = dropbox_oauth.exchange_code(code)
    except dropbox_oauth.DropboxAuthError as e:
        return _done_page(f"Dropbox sign-in failed: {e}", ok=False)

    name = email = None
    try:
        acct = dropbox_oauth.get_current_account(tok["access_token"])
        name = (acct.get("name") or {}).get("display_name")
        email = acct.get("email")
    except dropbox_oauth.DropboxAuthError:
        pass   # token still stored; account name is just a nicety

    conn = db.scalar(select(DropboxConnection))
    if conn is None:
        conn = DropboxConnection()
        db.add(conn)
    conn.account_name = name
    conn.account_email = email
    conn.access_token = tok["access_token"]
    conn.access_expires_at = tok["access_expires_at"]
    if tok.get("refresh_token"):
        conn.refresh_token = tok["refresh_token"]   # only present on the initial offline exchange
    conn.connected_by = emp.name
    conn.active = True
    db.commit()
    return _done_page(
        f"Connected to {name or email or 'your Dropbox'}. Photos will file under "
        f"{settings.dropbox_root}.", ok=True)


@router.get("/status")
def dropbox_status(db: DbSession = Depends(get_db),
                   emp: Employee = Depends(get_current_employee)) -> dict:
    """Owner-Hub reads this to show the Dropbox card (configured? connected? which account?)."""
    _require_owner(emp)
    conn = _active_connection(db)
    return {
        "configured": dropbox_oauth.is_configured(),
        "connected": bool(conn),
        "account_name": conn.account_name if conn else None,
        "account_email": conn.account_email if conn else None,
        "connected_by": conn.connected_by if conn else None,
        "root": settings.dropbox_root,
    }


@router.post("/disconnect")
def disconnect(request: Request, db: DbSession = Depends(get_db),
               emp: Employee = Depends(get_current_employee)) -> dict:
    """Owner disconnects Dropbox. Photo filing stops until reconnected."""
    require_owner_2fa(request, emp)
    conn = _active_connection(db)
    if conn is not None:
        conn.active = False
        db.commit()
    return {"disconnected": True}
