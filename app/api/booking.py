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
from sqlalchemy import select
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
    into_event_id: str | None = None   # complete a manager-made calendar event in place (backwards booking)


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
    if body.into_event_id:   # completing a hand-made calendar event — never double-book the same event
        dup = db.scalar(select(Job).where(Job.brand == body.brand, Job.gcal_event_id == body.into_event_id))
        if dup is not None:
            raise HTTPException(status_code=409, detail="That calendar event is already booked in the app.")
    job = service.create_booking(db, **body.model_dump())
    return BookingOut(
        id=str(job.id), headline=job.headline, status=job.status.value, gcal_event_id=job.gcal_event_id,
        calendar_error=(job.details or {}).get("_calendar_error"),
    )


def _prefill_from_event(ev: dict) -> dict:
    """Parse a (usually manager-created) calendar event into booking pre-fill: title, date, slot time,
    description. For a hand-made event the slot time IS the intended time (unlike app events, where the
    slot is positional and the real time is in the headline)."""
    start, end = ev.get("start") or {}, ev.get("end") or {}
    return {
        "event_id": ev.get("id"), "title": ev.get("summary") or "", "description": ev.get("description") or "",
        "on_date": (start.get("dateTime", "")[:10] or start.get("date") or None),
        "time_start": (start.get("dateTime", "")[11:16] or None),
        "time_end": (end.get("dateTime", "")[11:16] or None),
    }


@router.get("/from-event/{event_id}")
def from_event(event_id: str, db: DbSession = Depends(get_db),
               _mgr: Employee = Depends(require_manager)) -> dict:
    """Read a TEST-calendar event so the booking screen can pre-fill from a hand-made event."""
    from app.integrations import gcal
    try:
        ev = gcal.get_event(event_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"event not found ({type(exc).__name__})")
    out = _prefill_from_event(ev)
    out["already_booked"] = db.scalar(select(Job).where(Job.gcal_event_id == event_id)) is not None
    return out


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
