"""Reminders API — owner-facing. The CC-charge queue (§9/§11): list the 48-hour
residential-bin card-charge reminders and check them off. Creating/charging is never
automated here — the owner charges the card manually (guardrail §2)."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_employee
from app.auth.guards import is_owner
from app.db.session import get_db
from app.models.employee import Employee
from app.models.enums import Brand, ReminderKind
from app.models.reminder import Reminder
from app.reminders.service import add_cc_charge_reminder

router = APIRouter(prefix="/reminders", tags=["reminders"])


class CcChargeIn(BaseModel):
    invoice_date: date | None = None   # when the invoice was sent; defaults to today
    job_id: uuid.UUID | None = None
    name: str | None = None
    addr: str | None = None


def _owner_or_403(emp: Employee) -> Brand:
    if not is_owner(emp):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Owner access required")
    return emp.brand or Brand.victoria


def _out(r: Reminder) -> dict:
    return {"id": r.source_id, "kind": r.kind.value, "text": r.text, "by": r.by,
            "due": r.due.isoformat() if r.due else None, "done": r.done,
            "name": r.name, "addr": r.addr, "job_id": str(r.job_id) if r.job_id else None,
            "calendar": r.calendar}


@router.post("/cc-charge")
def create_cc_charge(body: CcChargeIn, db: DbSession = Depends(get_db),
                     emp: Employee = Depends(get_current_employee)) -> dict:
    """Start the 48-working-hour CC-charge clock for a residential bin — call this when you
    SEND the invoice. `due = invoice_date + 2 working days`. Idempotent per job. The charge
    itself stays manual (guardrail §2)."""
    brand = _owner_or_403(emp)
    inv = body.invoice_date or date.today()
    r = add_cc_charge_reminder(db, brand, invoice_date=inv, job_id=body.job_id,
                               name=body.name, addr=body.addr, by=emp.name, commit=True)
    return _out(r)


@router.get("")
def list_reminders(kind: ReminderKind | None = None, include_done: bool = False,
                   db: DbSession = Depends(get_db),
                   emp: Employee = Depends(get_current_employee)) -> dict:
    """List reminders for the owner (default: open only). Filter `kind=cc_charge` for the
    ready-to-charge queue."""
    brand = _owner_or_403(emp)
    q = select(Reminder).where(Reminder.brand == brand)
    if kind is not None:
        q = q.where(Reminder.kind == kind)
    if not include_done:
        q = q.where(Reminder.done.is_(False))
    q = q.order_by(Reminder.due.asc().nullslast())
    rows = db.scalars(q).all()
    return {"brand": brand.value, "count": len(rows), "reminders": [_out(r) for r in rows]}


@router.post("/{source_id}/done")
def mark_done(source_id: str, db: DbSession = Depends(get_db),
              emp: Employee = Depends(get_current_employee)) -> dict:
    """Owner checks off a reminder (e.g. the customer paid, or the card was charged manually).
    A paid CC-charge reminder turns its calendar event **purple** (best-effort)."""
    brand = _owner_or_403(emp)
    r = db.scalar(select(Reminder).where(Reminder.brand == brand, Reminder.source_id == source_id))
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No reminder '{source_id}'")
    r.done = True
    mirrored = False
    if r.kind == ReminderKind.cc_charge and r.gcal_event_id:
        try:
            from app.integrations import gcal
            gcal.recolor_reminder_event(r.gcal_event_id, gcal.CC_PAID_COLOR)  # -> purple/Grape
            mirrored = True
        except Exception:
            mirrored = False
    db.commit()
    return {"ok": True, "id": source_id, "done": True, "calendar_updated": mirrored}
