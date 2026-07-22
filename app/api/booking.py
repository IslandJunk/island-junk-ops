"""Booking API — creates a job and writes the single calendar event.

Manager-gated: the caller must have a session with manager (or owner) access. The
booking UI posts same-origin, so the session cookie rides along after PIN login.
"""
from __future__ import annotations

import uuid
from datetime import date, time
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from app.api.deps import require_manager
from app.booking import service
from app.db.session import get_db
from app.models.employee import Employee
from app.models.enums import AccountType, BookingLane, Brand, CustomerKind
from app.models.job import Job

router = APIRouter(prefix="/booking", tags=["booking"])


class BookingIn(BaseModel):
    brand: Brand
    on_date: date
    booking_lane: BookingLane = BookingLane.collect
    account_type: AccountType | None = None
    customer_kind: CustomerKind | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    customer_email: str | None = None
    address: str | None = None
    town: str | None = None
    scope: str | None = None
    est_price: Decimal | None = None
    crew: list[str] | None = None
    time_start: time | None = None
    time_end: time | None = None
    headline: str | None = None
    notes: str | None = None


class BookingOut(BaseModel):
    id: str
    headline: str
    status: str
    gcal_event_id: str | None
    calendar_error: str | None = None


@router.post("", response_model=BookingOut)
def create_booking(
    body: BookingIn,
    db: DbSession = Depends(get_db),
    _mgr: Employee = Depends(require_manager),
) -> BookingOut:
    job = service.create_booking(db, **body.model_dump())
    return BookingOut(
        id=str(job.id), headline=job.headline, status=job.status.value, gcal_event_id=job.gcal_event_id,
        calendar_error=(job.details or {}).get("_calendar_error"),
    )


class ConfirmTextIn(BaseModel):
    on_date: date


class ConfirmTextOut(BaseModel):
    sent: bool
    detail: str


@router.post("/{job_id}/text-confirmation", response_model=ConfirmTextOut)
def text_confirmation(
    job_id: str,
    body: ConfirmTextIn,
    db: DbSession = Depends(get_db),
    _mgr: Employee = Depends(require_manager),
) -> ConfirmTextOut:
    """Send the booking-confirmation text to the customer NOW — the manager taps the button on the
    booking screen after booking (never automatic, per Wes). Surfaces sent / dry-run / skipped."""
    try:
        jid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="job not found")
    job = db.get(Job, jid)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    try:
        res = service.send_confirmation_text(db, job, body.on_date)
    except Exception as exc:   # SmsGuardError or any send failure — show it on the button
        return ConfirmTextOut(sent=False, detail=f"{type(exc).__name__}: {exc}"[:200])
    if res.get("sent"):
        return ConfirmTextOut(sent=True, detail="dry-run (no Twilio creds yet)" if res.get("dry_run") else "text sent")
    return ConfirmTextOut(sent=False, detail=res.get("skipped") or "not sent")
