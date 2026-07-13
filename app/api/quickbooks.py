"""QuickBooks Online — Connect + status (WS4, OWNER-ONLY, READ-ONLY).

The owner connects a brand's QB company here so the app can READ it (detect invoice-sent + paid).
These routes never create/send an invoice — `/connect` + `/callback` do the OAuth handshake and
store a token; the sync layer only issues GETs. Everything rides on top of the existing manual
buttons, which stay the fallback (guardrail: QB is a layer, never a dependency).

CSRF: the OAuth `state` is a time-boxed signed token bound to the initiating owner's employee id,
so a forged/replayed callback can't attach a connection. The `ij_session` cookie is SameSite=Lax,
so it survives the top-level redirect back from Intuit and the callback resolves the owner.
"""
from __future__ import annotations

import html

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.api.deps import active_brand_for, get_current_employee
from app.auth.guards import is_owner
from app.core.config import settings
from app.db.session import get_db
from app.integrations import qbo
from app.models.employee import Employee
from app.models.enums import Brand
from app.models.qbo import QboConnection

router = APIRouter(prefix="/quickbooks", tags=["quickbooks"])

_state_serializer = URLSafeTimedSerializer(settings.session_secret, salt="ij-qbo-oauth")
_STATE_MAX_AGE = 900   # 15 min to complete the Intuit consent round-trip


def _require_owner(emp: Employee) -> None:
    if not is_owner(emp):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Owner only")


def _active_connection(db: DbSession, brand: Brand) -> QboConnection | None:
    return db.scalar(
        select(QboConnection).where(QboConnection.brand == brand, QboConnection.active.is_(True))
    )


def _done_page(message: str, ok: bool) -> HTMLResponse:
    """Small confirmation page the browser lands on after the OAuth round-trip, with a link back
    to the Owner Hub. ASCII only (served-page surrogate gotcha, PROGRESS.md §5)."""
    colour = "#3CA03C" if ok else "#C0392B"
    title = "QuickBooks connected" if ok else "QuickBooks not connected"
    msg = html.escape(message)   # message carries external text (Intuit ?error, company name, exception) — escape it
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
    """Owner taps 'Connect QuickBooks' -> redirect to Intuit consent. State is signed to this
    owner + the active brand so the callback can verify it and know which brand to attach."""
    _require_owner(emp)
    if not qbo.is_configured():
        return _done_page("QuickBooks isn't configured yet (missing client id/secret).", ok=False)
    brand = active_brand_for(request, emp)
    state = _state_serializer.dumps({"eid": str(emp.id), "brand": brand.value})
    return RedirectResponse(qbo.authorize_url(state), status_code=302)


@router.get("/callback")
def callback(request: Request, code: str | None = None, state: str | None = None,
             realmId: str | None = None, error: str | None = None,
             db: DbSession = Depends(get_db), emp: Employee = Depends(get_current_employee)) -> Response:
    """Intuit redirects here with an auth code + realmId. Verify state, exchange the code for a
    token, confirm the company, and store the connection. This is a token grant + reads only —
    never an invoice write."""
    _require_owner(emp)
    if error:
        return _done_page(f"QuickBooks consent was cancelled ({error}).", ok=False)
    if not (code and state and realmId):
        return _done_page("QuickBooks didn't return the expected code/state/company.", ok=False)
    try:
        data = _state_serializer.loads(state, max_age=_STATE_MAX_AGE)
    except SignatureExpired:
        return _done_page("The connect link expired — please tap Connect QuickBooks again.", ok=False)
    except BadSignature:
        return _done_page("The connect link was invalid — please try again.", ok=False)
    if data.get("eid") != str(emp.id):
        return _done_page("That connect link was started by a different account.", ok=False)
    if not realmId.isdigit():   # QBO realm ids are numeric — reject anything else before it reaches a URL/DB
        return _done_page("QuickBooks returned an unexpected company id.", ok=False)

    brand = Brand(data.get("brand") or Brand.victoria.value)
    try:
        tok = qbo.exchange_code(code)
    except qbo.QBOError as e:
        return _done_page(f"QuickBooks sign-in failed: {e}", ok=False)

    company_name = None
    try:
        company_name = qbo.company_info(realmId, tok["access_token"]).get("CompanyName")
    except qbo.QBOError:
        pass   # token still stored; company name is just a nicety

    conn = db.scalar(select(QboConnection).where(QboConnection.brand == brand))
    if conn is None:
        conn = QboConnection(brand=brand)
        db.add(conn)
    conn.realm_id = realmId
    conn.company_name = company_name
    conn.access_token = tok["access_token"]
    conn.access_expires_at = tok["access_expires_at"]
    conn.refresh_token = tok["refresh_token"]
    conn.refresh_expires_at = tok["refresh_expires_at"]
    conn.connected_by = emp.name
    conn.active = True
    db.commit()
    return _done_page(
        f"Connected to {company_name or ('company ' + realmId)} "
        f"({brand.value}, {settings.qbo_environment}). Auto-sync stays OFF until you switch it on.",
        ok=True)


@router.get("/status")
def qbo_status(request: Request, db: DbSession = Depends(get_db),
               emp: Employee = Depends(get_current_employee)) -> dict:
    """Owner-Hub reads this to show the QuickBooks card (connected? which company? auto-sync?)."""
    _require_owner(emp)
    brand = active_brand_for(request, emp)
    conn = _active_connection(db, brand)
    return {
        "configured": qbo.is_configured(),
        "environment": settings.qbo_environment,
        "connected": bool(conn),
        "company_name": conn.company_name if conn else None,
        "realm_id": conn.realm_id if conn else None,
        "auto_sync_enabled": bool(conn.auto_sync_enabled) if conn else False,
        "connected_by": conn.connected_by if conn else None,
        "brand": brand.value,
    }


@router.post("/disconnect")
def disconnect(request: Request, db: DbSession = Depends(get_db),
               emp: Employee = Depends(get_current_employee)) -> dict:
    """Owner disconnects QB for this brand. Auto-sync stops; the manual buttons carry on."""
    _require_owner(emp)
    brand = active_brand_for(request, emp)
    conn = _active_connection(db, brand)
    if conn is not None:
        conn.active = False
        conn.auto_sync_enabled = False
        db.commit()
    return {"disconnected": True}


@router.post("/sync-toggle")
def sync_toggle(request: Request, db: DbSession = Depends(get_db),
                emp: Employee = Depends(get_current_employee)) -> dict:
    """Owner flips QB auto-sync on/off for this brand. OFF (or disconnected) → the existing
    manual buttons do the same job (WS4 is a layer on top, never a dependency)."""
    _require_owner(emp)
    brand = active_brand_for(request, emp)
    conn = _active_connection(db, brand)
    if conn is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Connect QuickBooks first")
    conn.auto_sync_enabled = not conn.auto_sync_enabled
    db.commit()
    return {"auto_sync_enabled": conn.auto_sync_enabled}


@router.post("/sync")
def sync_now(request: Request, db: DbSession = Depends(get_db),
             emp: Employee = Depends(get_current_employee)) -> dict:
    """Owner taps 'Sync QuickBooks now' — a READ-ONLY pass over QBO invoices that starts the 48h
    clock for a newly-invoiced BIN-#### and clears it when that invoice is paid. Never writes to
    QBO, never charges a card (guardrail). Returns a summary {scanned, matched, started, paid}."""
    _require_owner(emp)
    brand = active_brand_for(request, emp)
    from app.quickbooks.sync import sync_brand
    return sync_brand(db, brand)
