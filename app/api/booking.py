"""Booking API — creates a job and writes the single calendar event.

Manager-gated: the caller must have a session with manager (or owner) access. The
booking UI posts same-origin, so the session cookie rides along after PIN login.
"""
from __future__ import annotations

from datetime import date, time
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from app.api.deps import require_manager
from app.booking import service
from app.db.session import get_db
from app.models.employee import Employee
from app.models.enums import AccountType, BookingLane, Brand, CustomerKind

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
