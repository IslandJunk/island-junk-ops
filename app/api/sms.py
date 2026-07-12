"""SMS API (SMS spec). Inbound Twilio webhook (auto-routes replies) + an owner/manager
outbound trigger that composes each message server-side from the locked templates (so the
brand-naming + no-card-number rules can't be bypassed by a client), + status/log reads.
"""
from __future__ import annotations

from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session as DbSession

from app.api.deps import active_brand_for, get_current_employee
from app.auth.guards import is_owner
from app.core.config import settings
from app.db.session import get_db
from app.models.employee import Employee
from app.models.enums import Brand
from app.models.sms import SmsMessage, SmsOptOut
from app.sms import service, templates

router = APIRouter(prefix="/sms", tags=["sms"])


def _twiml(reply: str | None) -> Response:
    body = f"<Message>{escape(reply)}</Message>" if reply else ""
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>'
    return Response(content=xml, media_type="application/xml")


@router.post("/inbound")
async def inbound(request: Request, db: DbSession = Depends(get_db)) -> Response:
    """Twilio inbound webhook (public, form-encoded). Handles the reply per spec §3 and
    returns TwiML for Twilio to deliver. Optionally validates the Twilio signature."""
    form = await request.form()
    if settings.twilio_validate_signatures and settings.twilio_auth_token:
        try:
            from twilio.request_validator import RequestValidator
            sig = request.headers.get("X-Twilio-Signature", "")
            valid = RequestValidator(settings.twilio_auth_token).validate(
                str(request.url), dict(form), sig)
        except Exception:
            valid = False
        if not valid:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid Twilio signature")
    from_number = str(form.get("From") or "")
    body = str(form.get("Body") or "")
    if not from_number:
        return _twiml(None)
    result = service.handle_inbound(db, from_number=from_number, body=body)
    return _twiml(result["reply"])


class SendIn(BaseModel):
    to: str
    kind: str
    params: dict = {}
    media_url: str | None = None    # e.g. the job photo for a completion text


@router.post("/send")
def send(body: SendIn, request: Request, db: DbSession = Depends(get_db),
         emp: Employee = Depends(get_current_employee)) -> dict:
    """Compose + send one automated message from the updates line (owner/manager). Dry-run
    (composed + logged, not sent) until Twilio creds are set."""
    if not (is_owner(emp) or "manager" in (emp.access or [])):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Manager/owner only")
    brand = active_brand_for(request, emp)
    try:
        text = templates.render(db, brand, body.kind, body.params)   # owner's wording, else built-in
    except (KeyError, ValueError) as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Bad message params: {e}")
    res = service.send(db, brand=brand, to=body.to, body=text, kind=body.kind, media_url=body.media_url)
    return {"to": body.to, "brand": brand.value, "kind": body.kind, "body": text, **res}


@router.get("/status")
def sms_status(emp: Employee = Depends(get_current_employee), db: DbSession = Depends(get_db)) -> dict:
    """Is texting live yet? (owner/manager) — surfaces the dry-run state + counts."""
    if not (is_owner(emp) or "manager" in (emp.access or [])):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Manager/owner only")
    return {
        "configured": settings.is_sms_configured,
        "mode": "live" if settings.is_sms_configured else "dry_run",
        "updates_line": settings.twilio_updates_line,
        "opted_out": db.scalar(select(func.count()).select_from(SmsOptOut)) or 0,
        "logged": db.scalar(select(func.count()).select_from(SmsMessage)) or 0,
    }


@router.get("/log")
def sms_log(limit: int = 50, db: DbSession = Depends(get_db),
            emp: Employee = Depends(get_current_employee)) -> dict:
    """Recent SMS log (owner only) — the inbound/outbound audit."""
    if not is_owner(emp):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Owner access required")
    rows = db.scalars(select(SmsMessage).order_by(desc(SmsMessage.created_at)).limit(min(limit, 200))).all()
    return {"count": len(rows), "messages": [{
        "direction": m.direction, "number": m.number, "brand": m.brand.value if m.brand else None,
        "kind": m.kind, "body": m.body, "sent": m.sent,
        "at": m.created_at.isoformat() if m.created_at else None,
    } for m in rows]}
