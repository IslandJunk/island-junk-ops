"""CC-charge reminder logic (CLAUDE.md §9/§11).

A residential bin is invoiced with 48 hours to pay by e-transfer; if unpaid, the card
on file is charged (+2.4%). The app **reminds** the owner at the 48-hour mark on a
separate off-board reminder calendar — it NEVER charges the card (guardrail §2.3).

This module creates that reminder in the app's `reminder` store (idempotently). The
Google reminder-calendar mirror is deferred until the reminder-calendar id is set
(see PROGRESS open decisions).
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models.enums import Brand, ReminderKind
from app.models.reminder import Reminder

# label for the separate off-board reminder calendar the owner checks (Google mirror TBD).
CC_CHARGE_CALENDAR = "cc-charge-reminders"
CC_CHARGE_WINDOW = timedelta(hours=48)


def cc_charge_source_id(*, job_id: uuid.UUID | None, name: str | None,
                        addr: str | None, drop_date: date) -> str:
    """Stable identity so re-triggering never duplicates (one per job, else per name+addr+date)."""
    if job_id is not None:
        return f"cc:{job_id}"
    return f"cc:{(name or '').strip().lower()}|{(addr or '').strip().lower()}|{drop_date.isoformat()}"


def add_cc_charge_reminder(db: DbSession, brand: Brand, *, drop_date: date,
                           job_id: uuid.UUID | None = None, name: str | None = None,
                           addr: str | None = None, by: str = "app",
                           commit: bool = False) -> Reminder:
    """Create the 48-hour CC-charge reminder (idempotent). `due = drop + 48h`.
    Pass commit=False to enlist it in the caller's transaction (e.g. booking)."""
    sid = cc_charge_source_id(job_id=job_id, name=name, addr=addr, drop_date=drop_date)
    existing = db.scalar(select(Reminder).where(Reminder.brand == brand, Reminder.source_id == sid))
    if existing is not None:
        return existing
    due = drop_date + CC_CHARGE_WINDOW
    who = name or "customer"
    text = (f"CC? UNPAID ({drop_date.isoformat()}) — residential bin: {who}. "
            f"E-transfer due by {due.isoformat()}; else charge card on file +2.4% (manual).")
    r = Reminder(brand=brand, source_id=sid, kind=ReminderKind.cc_charge, text=text, by=by,
                 due=due, name=name, addr=addr, job_id=job_id, calendar=CC_CHARGE_CALENDAR)
    db.add(r)
    if commit:
        db.commit()
        db.refresh(r)
    return r
