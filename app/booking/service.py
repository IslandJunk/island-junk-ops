"""Booking = the one place the app writes to the calendar.

Creates the Job row and writes exactly ONE event to the TEST calendar, stamping a
clean standard-format headline (the authoritative time). Every new job starts
**Sage / unassigned** (colorId 2) per the lifecycle — the manager assigns the truck
(colour) and stacks it on the calendar afterwards; the app never rewrites it again.
"""
from __future__ import annotations

import re
from datetime import date, time
from decimal import Decimal

from sqlalchemy.orm import Session as DbSession

from app.integrations import gcal
from app.models.enums import AccountType, BookingLane, Brand, CustomerKind, JobStatus
from app.models.job import Job

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


def _friendly_time(t: time | None) -> str:
    if t is None:
        return ""
    h = t.hour % 12 or 12
    ap = "am" if t.hour < 12 else "pm"
    return f"{h}:{t.minute:02d}{ap}" if t.minute else f"{h}{ap}"


def _confirm_when(on_date: date, ts: time | None, te: time | None) -> str:
    day = on_date.strftime("%a %b ") + str(on_date.day)
    if ts and te:
        return f"{day}, {_friendly_time(ts)}–{_friendly_time(te)}"
    if ts:
        return f"{day}, {_friendly_time(ts)}"
    return day


def _send_booking_confirmation(db: DbSession, job: Job, on_date: date) -> None:
    """Text the customer a booking confirmation from the updates line (best-effort, dry-run
    until Twilio creds). Never fails the booking — a texting error is swallowed."""
    if not job.customer_phone:
        return
    try:
        from app.sms import service as sms_service, templates as sms_templates
        body = sms_templates.render(db, job.brand, "booking_confirm", {
            "name": job.customer_name,
            "when": _confirm_when(on_date, job.time_start, job.time_end),
            "address": job.address})
        sms_service.send(db, brand=job.brand, to=job.customer_phone, body=body, kind="booking_confirm")
    except Exception:
        pass


# Summary lines that reveal a price. Stripped from the calendar event on lanes whose crew must
# NOT see pricing (commercial/invoiced, bins) — CLAUDE.md §12. Residential hand-load (the collect
# lane) is exempt: that crew collects on site and is shown the price. (Anything with a "$" is also
# treated as a price line, belt-and-suspenders.)
_PRICE_LABEL = re.compile(r"^\s*(PRICE|EST|ESTIMATE|SUBTOTAL|TOTAL|GST|CARD FEE|DUMP FEE|CREW HEADS-UP / EST)\b", re.I)


def _is_price_line(ln: str) -> bool:
    return bool(_PRICE_LABEL.match(ln)) or ("$" in ln)


def _description(job: Job) -> str:
    """The calendar event body IS the job's living record: the manager's full booking detail, a
    `NOTES:` section they can fill in on Google Calendar afterward (read back onto the job so the
    crew see it), and the Dropbox photos link. The detail mirrors the review summary on job.notes;
    price lines are dropped for lanes whose crew must not see pricing. No machine tag — events link
    to their job by the Google event id (gcal_event_id), so nothing cryptic is shown."""
    notes = (job.notes or "").strip()
    show_price = job.booking_lane == BookingLane.collect   # residential collect: crew see pricing
    lines: list[str] = []
    if notes:
        for ln in notes.split("\n"):
            if not show_price and _is_price_line(ln):
                continue
            lines.append(ln)
    else:   # fallback for events not created from the app's review summary
        lines.append(f"{job.booking_lane.value.upper()} booking")
        if job.customer_name:
            lines.append(f"Customer: {job.customer_name}")
        if job.customer_phone:
            lines.append(f"Phone: {job.customer_phone}")
        if job.address:
            lines.append(f"Address: {job.address}")
    link = ((job.details or {}).get("dropbox") or {}).get("link")
    if link and "Photos:" not in "\n".join(lines):
        lines.append(f"Photos: {link}")   # tap in Calendar -> the job's photo folder
    lines.append("")
    lines.append("NOTES:")   # manager adds notes here on Calendar; the crew see them on the job
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
    try:   # Dropbox per-job folder + shared link — best-effort, dry-run/no-op until connected
        from app.integrations import dropbox_files
        dropbox_files.ensure_job_folder(db, job, on_date)
    except Exception:
        pass   # Dropbox is a nicety — a failure here never fails the booking
    if write_calendar:
        try:
            job.gcal_event_id = gcal.create_event(
                summary=headline, description=_description(job), color_id=SAGE_COLOR_ID,
                on_date=on_date, start_time=time_start, end_time=time_end,
            )
        except Exception as exc:
            # Don't lose the booking on a calendar hiccup — the Job is still saved; record the
            # error so the UI + logs surface it (previously this 500'd and the button faked success).
            import logging
            logging.getLogger("booking").exception("calendar write failed")
            job.gcal_event_id = None
            d = dict(job.details or {})
            d["_calendar_error"] = f"{type(exc).__name__}: {exc}"[:400]
            job.details = d
    # NOTE: the §9/§11 CC-charge reminder is NOT created here. Per Wes, the 48-working-hour
    # clock starts when the owner SENDS THE INVOICE (after pickup, sometimes days later),
    # not at booking/drop — so it's created via POST /reminders/cc-charge at invoice time.
    db.commit()
    db.refresh(job)
    _send_booking_confirmation(db, job, on_date)
    return job
