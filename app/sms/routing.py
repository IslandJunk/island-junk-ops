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


def find_brand_for_number(db: DbSession, number: str) -> Brand | None:
    """Which brand's customer is this? Match the inbound number against residential + company
    customer phones by last-10-digits. Returns None if unrecognised (spec §3 → list both)."""
    want = digits10(number)
    if not want:
        return None
    for r in db.scalars(select(ResidentialCustomer).where(ResidentialCustomer.phone.isnot(None))):
        if digits10(r.phone) == want:
            return r.brand
    for c in db.scalars(select(CompanyCustomer).where(CompanyCustomer.phone.isnot(None))):
        if digits10(c.phone) == want:
            return c.brand
    return None


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
