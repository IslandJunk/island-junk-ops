"""Inbound reply routing (SMS spec §3). The updates line is send-only, so an inbound text
is handled automatically: STOP/HELP FIRST (compliance §5), otherwise an "unmonitored line"
auto-reply that points the customer to the RIGHT main line by recognising who they are.

Kept pure where possible (classification + reply text) so it unit-tests without Twilio/DB.
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.config import settings
from app.models.customer import CompanyCustomer, ResidentialCustomer
from app.models.enums import Brand

# Compliance keywords (spec §5). Matched on the first word, case-insensitive.
STOP_WORDS = {"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT", "OPTOUT", "OPT-OUT", "REVOKE"}
START_WORDS = {"START", "UNSTOP", "YES", "OPTIN", "OPT-IN"}
HELP_WORDS = {"HELP", "INFO"}


def classify(body: str | None) -> str:
    """-> 'stop' | 'start' | 'help' | 'reply' (STOP/HELP handled before the redirect)."""
    first = (body or "").strip().upper().split()
    word = first[0] if first else ""
    if word in STOP_WORDS:
        return "stop"
    if word in START_WORDS:
        return "start"
    if word in HELP_WORDS:
        return "help"
    return "reply"


def digits10(s: str | None) -> str:
    """Last 10 digits (NANP) of a number, for matching a Twilio E.164 inbound against a
    customer's stored phone regardless of formatting."""
    d = re.sub(r"\D", "", s or "")
    return d[-10:] if len(d) >= 10 else d


def find_customer_context(db: DbSession, number: str) -> dict | None:
    """Who texted us? Match the inbound number against residential + company customer phones
    by last-10-digits → {name, address, brand}. This is what lets the manager nudge say WHO
    it's from (spec §3.3). None if unrecognised."""
    want = digits10(number)
    if not want:
        return None
    for r in db.scalars(select(ResidentialCustomer).where(ResidentialCustomer.phone.isnot(None))):
        if digits10(r.phone) == want:
            name = f"{r.first or ''} {r.last or ''}".strip()
            return {"name": name or None, "address": r.addr, "brand": r.brand}
    for c in db.scalars(select(CompanyCustomer).where(CompanyCustomer.phone.isnot(None))):
        if digits10(c.phone) == want:
            return {"name": c.co, "address": c.addr, "brand": c.brand}
    return None


def find_brand_for_number(db: DbSession, number: str) -> Brand | None:
    """Just the brand of a recognised customer (spec §3 → None → list both main lines)."""
    ctx = find_customer_context(db, number)
    return ctx["brand"] if ctx else None


def _name_key(name: str | None) -> str:
    """Normalise a customer name for matching: lowercase, non-alphanumerics stripped
    (so 'Jade Smith' and 'jade  smith' collapse to the same key)."""
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def customer_phone_by_name(db: DbSession, brand: Brand, name: str | None) -> str | None:
    """A customer's phone iff EXACTLY ONE customer (residential OR company) in this brand
    matches `name` (normalised). Mirrors the review name→phone resolver
    (sync_handlers._review_phone_index) so the residential completion text can reach the
    customer without a phone field on the calculator. Ambiguous (>1 match) or absent → None,
    and the caller falls back to a manually-entered number (the confirm-number step)."""
    key = _name_key(name)
    if not key:
        return None
    found: str | None = None
    count = 0
    for r in db.scalars(select(ResidentialCustomer).where(
            ResidentialCustomer.brand == brand, ResidentialCustomer.phone.isnot(None))):
        if _name_key(f"{r.first or ''} {r.last or ''}") == key:
            count += 1
            found = r.phone
            if count > 1:
                return None
    for c in db.scalars(select(CompanyCustomer).where(
            CompanyCustomer.brand == brand, CompanyCustomer.phone.isnot(None))):
        if _name_key(c.co) == key:
            count += 1
            found = c.phone
            if count > 1:
                return None
    return found if count == 1 else None


def _fmt(e164: str) -> str:
    """+17789665865 -> 778-966-5865 for display in the reply."""
    d = re.sub(r"\D", "", e164 or "")
    ten = d[-10:]
    return f"{ten[0:3]}-{ten[3:6]}-{ten[6:10]}" if len(ten) == 10 else e164


def auto_reply_text(brand: Brand | None) -> str:
    """The 'unmonitored line' redirect (spec §3.2). Recognised → that brand's main line;
    unrecognised → list both."""
    vic, nan = _fmt(settings.victoria_main_line), _fmt(settings.nanaimo_main_line)
    lead = "Thanks for the reply! This is Island Junk's automated text line, so it isn't monitored."
    if brand == Brand.victoria:
        return f"{lead} To reach our crew, call or text us at {vic} and we'll help you out."
    if brand == Brand.nanaimo:
        return f"{lead} To reach our crew, call or text us at {nan} and we'll help you out."
    return (f"{lead} To reach our crew, call or text Island Junk Solutions (Victoria) at {vic} "
            f"or Island Junk Nanaimo at {nan}.")


def help_text() -> str:
    """HELP reply — business info (spec §5)."""
    vic, nan = _fmt(settings.victoria_main_line), _fmt(settings.nanaimo_main_line)
    return (f"Island Junk automated updates. This line is send-only. Victoria: {vic} · "
            f"Nanaimo: {nan}. Reply STOP to opt out.")


def stop_confirm_text() -> str:
    return "You've been opted out of Island Junk automated texts. Reply START to opt back in."


def start_confirm_text() -> str:
    return "You're opted back in to Island Junk automated texts. Reply STOP to opt out."
