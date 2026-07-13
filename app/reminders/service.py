"""CC-charge reminder logic (CLAUDE.md §9/§11, refined with Wes 2026-07).

A residential bin is invoiced after pickup with 48 hours to pay by e-transfer; if
unpaid, the card on file is charged (+2.4%). Two rules from Wes:
  - the 48-hour clock starts **when the invoice is sent**, NOT at drop or pickup — a bin
    can sit in the yard a day or two before he invoices it;
  - "48 hours" means **2 working days** (weekends + BC stat holidays don't count).
So the reminder is created at invoice time with `due = invoice_date + 2 working days`.

The app only **reminds**; it NEVER charges the card (guardrail §2.3). The Google
reminder-calendar mirror is deferred until the reminder-calendar id is set.
"""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.dates import add_business_days
from app.models.enums import Brand, ReminderKind
from app.models.reminder import Reminder

# label for the separate off-board reminder calendar the owner checks (Google mirror TBD).
CC_CHARGE_CALENDAR = "cc-charge-reminders"
CC_CHARGE_WORKING_DAYS = 2


def cc_charge_source_id(*, job_id: uuid.UUID | None, name: str | None,
                        addr: str | None, invoice_date: date) -> str:
    """Stable identity so re-triggering never duplicates (one per job, else per name+addr+invoice date)."""
    if job_id is not None:
        return f"cc:{job_id}"
    return f"cc:{(name or '').strip().lower()}|{(addr or '').strip().lower()}|{invoice_date.isoformat()}"


def add_cc_charge_reminder(db: DbSession, brand: Brand, *, invoice_date: date,
                           job_id: uuid.UUID | None = None, name: str | None = None,
                           addr: str | None = None, by: str = "app",
                           reference_code: str | None = None,
                           commit: bool = False) -> Reminder:
    """Create the CC-charge reminder when a residential-bin invoice is sent (idempotent).
    `due = invoice_date + 2 working days`. `reference_code` = the BIN-xxxx QB match key so WS4
    (and the owner, in QuickBooks) can tie the invoice/payment back to this reminder."""
    sid = cc_charge_source_id(job_id=job_id, name=name, addr=addr, invoice_date=invoice_date)
    existing = db.scalar(select(Reminder).where(Reminder.brand == brand, Reminder.source_id == sid))
    if existing is not None:
        if reference_code and not existing.reference_code:
            existing.reference_code = reference_code   # backfill the code onto a prior reminder
            if commit:
                db.commit()
        return existing
    due = add_business_days(invoice_date, CC_CHARGE_WORKING_DAYS)
    who = name or "customer"
    text = (f"CC? UNPAID ({invoice_date.isoformat()}) — residential bin: {who}. "
            f"Invoiced {invoice_date.isoformat()}; e-transfer due by {due.isoformat()} "
            f"(2 working days); else charge card on file +2.4% (manual).")
    r = Reminder(brand=brand, source_id=sid, kind=ReminderKind.cc_charge, text=text, by=by,
                 due=due, name=name, addr=addr, job_id=job_id, reference_code=reference_code,
                 calendar=CC_CHARGE_CALENDAR)
    db.add(r)
    _mirror_to_calendar(r, due, who, text)   # best-effort; DB reminder saves regardless
    if commit:
        db.commit()
        db.refresh(r)
    return r


def _mirror_to_calendar(reminder: Reminder, due: date, who: str, text: str) -> None:
    """Create the reminder event on the off-board reminder calendar. Best-effort: if the
    service account can't reach the calendar yet (not shared), the DB reminder still saves
    and the event can be back-filled later. Never raises."""
    try:
        from app.integrations import gcal
        reminder.gcal_event_id = gcal.create_reminder_event(
            summary=f"CC? UNPAID — {who}", description=text,
            on_date=due, color_id=gcal.CC_UNPAID_COLOR)
    except Exception:
        pass
