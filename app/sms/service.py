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

from app.core.config import settings
from app.integrations import twilio_sms
from app.models.enums import Brand
from app.models.sms import SmsMessage, SmsOptOut
from app.sms import messages, routing


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


def _notify_number(brand: Brand | None) -> str | None:
    """Where to forward a customer reply so the manager isn't guessing. Per-brand override,
    else the brand's main line (the manager's phone). Blank string in .env disables it."""
    if brand == Brand.nanaimo:
        n = settings.manager_notify_nanaimo
        return (n if n is not None else settings.nanaimo_main_line) or None
    n = settings.manager_notify_victoria
    return (n if n is not None else settings.victoria_main_line) or None


def _nudge_manager(db: DbSession, *, from_number: str, body: str, brand: Brand | None,
                   ctx: dict | None) -> None:
    """Forward an inbound customer reply to the manager WITH who-it-is + address (spec §3.3),
    so a bare 'I'm not home, 45 min' has a name + job attached. Best-effort, from the updates
    line. Never texts a MAIN line it's not supposed to (send_raw's from-guard still applies)."""
    to = _notify_number(brand)
    if not to:
        return
    who = (ctx or {}).get("name") or "an unknown number"
    addr = (ctx or {}).get("address")
    bname = messages.brand_name(brand) if brand else "Island Junk"
    disp = routing._fmt(from_number) if from_number.startswith("+") else from_number
    text = (f"📱 {bname} — reply from {who} ({disp})"
            + (f" · {addr}" if addr else "")
            + f":\n\"{body.strip()}\"\n(Automated line; text them back from your line.)")
    try:
        res = twilio_sms.send_raw(to=to, body=text)
        _log(db, direction="out", number=to, brand=brand, kind="manager_nudge",
             body=text, sid=res.get("sid"), sent=bool(res.get("sent")))
    except Exception:
        pass


def handle_inbound(db: DbSession, *, from_number: str, body: str) -> dict:
    """Answer an inbound to the updates line (spec §3). Logs the inbound + the reply, applies
    STOP/START opt-out, forwards real replies to the manager WITH context, and RETURNS the
    reply text — the webhook sends it back as TwiML. STOP/HELP handled first."""
    cls = routing.classify(body)
    ctx = routing.find_customer_context(db, from_number)
    brand = ctx["brand"] if ctx else None
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
        # A real message (not a compliance keyword) → nudge the manager with who + job context.
        _nudge_manager(db, from_number=from_number, body=body, brand=brand, ctx=ctx)

    # Log the reply as an outbound (the webhook returns it via TwiML for Twilio to deliver).
    _log(db, direction="out", number=from_number, brand=brand, kind=kind, body=reply, sid=None, sent=True)
    db.commit()
    return {"action": cls, "brand": brand.value if brand else None, "reply": reply,
            "nudged": kind == "auto_reply"}
