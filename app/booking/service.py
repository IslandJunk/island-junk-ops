"""Booking = the one place the app writes to the calendar.

Creates the Job row and writes exactly ONE event to the TEST calendar, stamping a
clean standard-format headline (the authoritative time). Every new job starts
**Sage / unassigned** (colorId 2) per the lifecycle — the manager assigns the truck
(colour) and stacks it on the calendar afterwards; the app never rewrites it again.
"""
from __future__ import annotations

from datetime import date, time
from decimal import Decimal

from sqlalchemy.orm import Session as DbSession

from app.integrations import gcal
from app.models.enums import AccountType, BookingLane, Brand, CustomerKind, JobStatus
from app.models.job import Job
from app.reminders.service import add_cc_charge_reminder

SAGE_COLOR_ID = 2  # locked Unassigned — every new job starts here


def _fmt_time(t: time | None) -> str:
    """time -> headline token, fixed workday, no am/pm (8:00 -> '8', 12:30 -> '1230')."""
    if t is None:
        return ""
    return str(t.hour) if t.minute == 0 else f"{t.hour}{t.minute:02d}"


def build_headline(time_start: time | None, time_end: time | None,
                   customer_name: str | None, scope: str | None) -> str:
    tt = _fmt_time(time_start)
    if time_end:
        tt = f"{tt}-{_fmt_time(time_end)}"
    parts = [p for p in (tt, customer_name) if p]
    head = " - ".join(parts) if parts else (customer_name or "Job")
    if scope:
        head += f" ({scope[:40]})"
    return head


def _description(job: Job) -> str:
    lines = [f"{job.booking_lane.value.upper()} booking"]
    if job.customer_name:
        lines.append(f"Customer: {job.customer_name}")
    if job.customer_phone:
        lines.append(f"Phone: {job.customer_phone}")
    if job.address:
        lines.append(f"Address: {job.address}")
    if job.scope:
        lines.append(f"Scope: {job.scope}")
    if job.est_price is not None:
        lines.append(f"Est: ${job.est_price}")
    if job.crew:
        lines.append(f"Crew: {', '.join(job.crew)}")
    lines.append(f"[app job {job.id}]")
    return "\n".join(lines)


def create_booking(
    db: DbSession, *, brand: Brand, on_date: date,
    booking_lane: BookingLane = BookingLane.collect,
    account_type: AccountType | None = None,
    customer_kind: CustomerKind | None = None,
    customer_name: str | None = None, customer_phone: str | None = None, customer_email: str | None = None,
    address: str | None = None, town: str | None = None, scope: str | None = None,
    est_price: Decimal | None = None, crew: list[str] | None = None,
    time_start: time | None = None, time_end: time | None = None, notes: str | None = None,
    headline: str | None = None, write_calendar: bool = True,
) -> Job:
    # Use the caller's headline verbatim if given (the booking UI stamps its own,
    # matching the prototype exactly); otherwise build the standard format.
    headline = headline or build_headline(time_start, time_end, customer_name, scope)
    job = Job(
        brand=brand, booking_lane=booking_lane, account_type=account_type, status=JobStatus.unassigned,
        customer_kind=customer_kind, customer_name=customer_name, customer_phone=customer_phone,
        customer_email=customer_email, address=address, town=town, scope=scope, est_price=est_price,
        crew=crew, time_start=time_start, time_end=time_end, headline=headline, notes=notes,
    )
    db.add(job)
    db.flush()  # assign job.id for the description
    if write_calendar:
        job.gcal_event_id = gcal.create_event(
            summary=headline, description=_description(job), color_id=SAGE_COLOR_ID,
            on_date=on_date, start_time=time_start, end_time=time_end,
        )
    # §9/§11: a residential bin gets a 48-hour CC-charge reminder (charge stays manual).
    if account_type == AccountType.residential_bin:
        add_cc_charge_reminder(db, brand, drop_date=on_date, job_id=job.id,
                               name=customer_name, addr=address, by="booking")
    db.commit()
    db.refresh(job)
    return job
