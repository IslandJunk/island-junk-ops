"""SMS service — opt-out enforcement, send + audit log, and inbound orchestration.

Every OUTBOUND automated message is opt-out-checked (spec §5) and logged. Every INBOUND is
logged, then answered per spec §3: STOP/HELP first, else the unmonitored-line redirect. The
actual send goes through `twilio_sms.send_raw` (send-only, from the updates line, dry-run
until creds).
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.integrations import twilio_sms
from app.models.enums import Brand
from app.models.sms import SmsMessage, SmsOptOut
from app.sms import routing


def to_e164(number: str | None) -> str:
    """Best-effort E.164 for a NANP number, so opt-out matching + logging are consistent."""
    raw = (number or "").strip()
    d = re.sub(r"\D", "", raw)
    if raw.startswith("+"):
        return "+" + d
    if len(d) == 10:
        return "+1" + d
    if len(d) == 11 and d.startswith("1"):
        return "+" + d
    return ("+" + d) if d else ""


def is_opted_out(db: DbSession, number: str) -> bool:
    return db.scalar(select(SmsOptOut).where(SmsOptOut.number == to_e164(number))) is not None


def opt_out(db: DbSession, number: str) -> None:
    n = to_e164(number)
    if not n or db.scalar(select(SmsOptOut).where(SmsOptOut.number == n)):
        return
    db.add(SmsOptOut(number=n))


def opt_in(db: DbSession, number: str) -> None:
    row = db.scalar(select(SmsOptOut).where(SmsOptOut.number == to_e164(number)))
    if row is not None:
        db.delete(row)


def _log(db: DbSession, *, direction: str, number: str, brand: Brand | None, kind: str | None,
         body: str | None, sid: str | None, sent: bool) -> SmsMessage:
    m = SmsMessage(direction=direction, number=to_e164(number), brand=brand, kind=kind,
                   body=body, twilio_sid=sid, sent=sent)
    db.add(m)
    return m


def send(db: DbSession, *, brand: Brand | None, to: str, body: str, kind: str,
         media_url: str | None = None, respect_opt_out: bool = True) -> dict:
    """Send one automated message from the updates line + log it. Skips (logs, doesn't send)
    if the number opted out. `respect_opt_out=False` is for direct compliance replies
    (STOP/HELP confirmations, the redirect answer to an inbound)."""
    if respect_opt_out and is_opted_out(db, to):
        _log(db, direction="out", number=to, brand=brand, kind=kind, body=body, sid=None, sent=False)
        db.commit()
        return {"sent": False, "skipped": "opted_out", "dry_run": False}
    try:
        res = twilio_sms.send_raw(to=to, body=body, media_url=media_url)
    except twilio_sms.SmsGuardError:
        _log(db, direction="out", number=to, brand=brand, kind=kind, body=body, sid=None, sent=False)
        db.commit()
        raise
    _log(db, direction="out", number=to, brand=brand, kind=kind, body=body,
         sid=res.get("sid"), sent=bool(res.get("sent")))
    db.commit()
    return res


def handle_inbound(db: DbSession, *, from_number: str, body: str) -> dict:
    """Answer an inbound to the updates line (spec §3). Logs the inbound + the reply, applies
    STOP/START opt-out, and RETURNS the reply text — the webhook sends it back as TwiML (so
    Twilio delivers it; no separate send call, no double-send). STOP/HELP handled first."""
    cls = routing.classify(body)
    brand = routing.find_brand_for_number(db, from_number)
    _log(db, direction="in", number=from_number, brand=brand, kind=cls, body=body, sid=None, sent=True)

    if cls == "stop":
        opt_out(db, from_number)
        reply, kind = routing.stop_confirm_text(), "stop"
    elif cls == "start":
        opt_in(db, from_number)
        reply, kind = routing.start_confirm_text(), "start"
    elif cls == "help":
        reply, kind = routing.help_text(), "help"
    else:
        reply, kind = routing.auto_reply_text(brand), "auto_reply"

    # Log the reply as an outbound (the webhook returns it via TwiML for Twilio to deliver).
    _log(db, direction="out", number=from_number, brand=brand, kind=kind, body=reply, sid=None, sent=True)
    db.commit()
    return {"action": cls, "brand": brand.value if brand else None, "reply": reply}
