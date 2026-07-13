"""QuickBooks Online — READ-ONLY sync engine (WS4).

Reads QBO to drive the residential-bin 48-hour clock WITHOUT ever writing to QBO or charging a
card:
  * an invoice carrying BIN-#### is unpaid       -> START the 48h cc_charge reminder
  * that invoice is fully paid (Balance == 0)    -> CLEAR the reminder + mark paid
Matching is by the BIN-#### code the owner pastes into the invoice (memo / PO / custom field /
line description). Every action mirrors what the owner's manual buttons already do — QB is a
layer, never a dependency (guardrail). Token refresh lives here too. Nothing here POSTs to any
QBO /invoice or /payment resource — reads only.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.integrations import qbo
from app.models.enums import Brand, ReminderKind
from app.models.qbo import QboConnection
from app.models.reminder import Reminder
from app.reminders.service import add_cc_charge_reminder

# Bounded digit count on purpose: reference_code columns are varchar(20) ("BIN-" + <=15 digits =
# 19). An unbounded BIN-\d+ from a malformed/hostile invoice would overflow the column and crash
# the whole sync batch on commit (same failure class as the source_id truncation bug).
_REF_RE = re.compile(r"BIN-\d{1,15}", re.IGNORECASE)
_FIRST_RUN_LOOKBACK_DAYS = 90


def _active_connection(db: DbSession, brand: Brand) -> QboConnection | None:
    return db.scalar(select(QboConnection).where(
        QboConnection.brand == brand, QboConnection.active.is_(True)))


def get_valid_access_token(db: DbSession, conn: QboConnection) -> str:
    """Return a usable access token, refreshing (and persisting the ROTATED refresh token) when
    it's expired or about to be. Raises qbo.QBOError if the refresh fails (needs re-auth)."""
    now = datetime.now(timezone.utc)
    if conn.access_token and conn.access_expires_at and conn.access_expires_at > now + timedelta(seconds=120):
        return conn.access_token
    tok = qbo.refresh(conn.refresh_token)
    conn.access_token = tok["access_token"]
    conn.access_expires_at = tok["access_expires_at"]
    conn.refresh_token = tok["refresh_token"]
    conn.refresh_expires_at = tok["refresh_expires_at"]
    db.commit()
    return conn.access_token


def _extract_ref(inv: dict) -> str | None:
    """Find BIN-#### anywhere the owner might have put it on the invoice."""
    candidates = [inv.get("DocNumber"), inv.get("PrivateNote")]
    memo = inv.get("CustomerMemo")
    if isinstance(memo, dict):
        candidates.append(memo.get("value"))
    for cf in inv.get("CustomField") or []:
        if isinstance(cf, dict):
            candidates.append(cf.get("StringValue"))
    for line in inv.get("Line") or []:
        if isinstance(line, dict):
            candidates.append(line.get("Description"))
    for c in candidates:
        if c:
            m = _REF_RE.search(str(c))
            if m:
                return m.group(0).upper()
    return None


def _bill_addr(inv: dict) -> str | None:
    a = inv.get("BillAddr")
    if not isinstance(a, dict):
        return None
    parts = [a.get("Line1"), a.get("City"), a.get("CountrySubDivisionCode"), a.get("PostalCode")]
    joined = ", ".join(p for p in parts if p)
    return joined or None


def _invoice_date(inv: dict) -> date:
    txn = inv.get("TxnDate")
    if txn:
        try:
            return date.fromisoformat(str(txn)[:10])
        except ValueError:
            pass
    return date.today()


def _mark_reminder_paid(r: Reminder) -> None:
    """Same close-out the owner's 'Received as e-transfer' button does: mark done, and (best-
    effort) turn the reminder-calendar event purple. Never charges anything."""
    r.done = True
    if r.kind == ReminderKind.cc_charge and r.gcal_event_id:
        try:
            from app.integrations import gcal
            gcal.recolor_reminder_event(r.gcal_event_id, gcal.CC_PAID_COLOR)
        except Exception:
            pass


def sync_brand(db: DbSession, brand: Brand) -> dict:
    """READ-ONLY pass over QBO invoices changed since the last sync; start/clear the 48h reminder
    by BIN-#### match. Returns a summary. Never raises for 'not connected' — returns a reason so
    the owner button can show it. Matching a reminder is by `reference_code` (so the manual and
    QB paths never double-create)."""
    conn = _active_connection(db, brand)
    if conn is None:
        return {"ok": False, "reason": "not_connected"}
    if not qbo.is_configured():
        return {"ok": False, "reason": "not_configured"}

    now = datetime.now(timezone.utc)
    since = conn.last_synced_at or (now - timedelta(days=_FIRST_RUN_LOOKBACK_DAYS))
    since_iso = since.astimezone(timezone.utc).replace(microsecond=0).isoformat()

    try:
        token = get_valid_access_token(db, conn)
        sql = f"SELECT * FROM Invoice WHERE MetaData.LastUpdatedTime >= '{since_iso}' MAXRESULTS 1000"
        resp = qbo.query(conn.realm_id, token, sql)
    except qbo.QBOError as e:
        return {"ok": False, "reason": f"qbo_error: {e}"}

    invoices = resp.get("Invoice") or []
    scanned = matched = started = paid = 0
    for inv in invoices:
        scanned += 1
        code = _extract_ref(inv)
        if not code:
            continue
        matched += 1
        try:
            balance = float(inv.get("Balance") or 0)
            total = float(inv.get("TotalAmt") or 0)
        except (TypeError, ValueError):
            balance, total = 0.0, 0.0
        is_paid = total > 0 and balance == 0

        existing = db.scalar(select(Reminder).where(
            Reminder.brand == brand, Reminder.kind == ReminderKind.cc_charge,
            Reminder.reference_code == code))

        if is_paid:
            if existing is not None and not existing.done:
                _mark_reminder_paid(existing)
                paid += 1
        elif existing is None:
            cust = inv.get("CustomerRef") or {}
            add_cc_charge_reminder(
                db, brand, invoice_date=_invoice_date(inv),
                name=(cust.get("name") if isinstance(cust, dict) else None),
                addr=_bill_addr(inv), by="quickbooks", reference_code=code)
            started += 1

    conn.last_synced_at = now
    db.commit()
    return {"ok": True, "scanned": scanned, "matched": matched, "started": started,
            "paid": paid, "company": conn.company_name}
