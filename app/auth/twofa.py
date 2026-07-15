"""Owner SMS two-factor auth — a real second factor for the owner account.

The owner already has a PIN (first factor, like everyone). This adds a second factor: a 6-digit
code texted to the owner's phone, verified server-side, that unlocks the Owner Hub + the most
sensitive owner actions (card charging, QuickBooks) for the CURRENT session. Crew never touch it.
Codes are HMAC-hashed (key = session secret, which lives in env, not the DB) and short-lived;
backup codes (OwnerSecurity.backup_codes) work when the phone is unavailable.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.models.owner_security import OwnerSecurity
from app.models.session import Session as AuthSession

CODE_TTL_MINUTES = 10


def _owner_security(db: DbSession) -> OwnerSecurity | None:
    return db.scalar(select(OwnerSecurity))


def _hash_code(code: str) -> str:
    return hmac.new(settings.session_secret.encode(), code.encode(), hashlib.sha256).hexdigest()


def owner_phone(db: DbSession) -> str | None:
    sec = _owner_security(db)
    if sec and sec.phones:
        return (sec.phones[0] or {}).get("number") or None
    return None


def mask_phone(number: str | None) -> str | None:
    if not number:
        return None
    d = "".join(ch for ch in number if ch.isdigit())
    return ("(...) ...-" + d[-4:]) if len(d) >= 4 else "..."


def set_owner_phone(db: DbSession, number: str) -> None:
    """Store/replace the owner's 2FA phone. Creates the OwnerSecurity row if missing."""
    sec = _owner_security(db)
    if sec is None:
        sec = OwnerSecurity(password_hash="", phones=[], backup_codes=[], audit_log=[])
        db.add(sec)
    sec.phones = [{"id": "primary", "label": "cell", "number": number.strip()}]
    db.commit()


def owner_email(db: DbSession) -> str | None:
    sec = _owner_security(db)
    if sec and sec.emails:
        return (sec.emails[0] or {}).get("address") or None
    return None


def mask_email(address: str | None) -> str | None:
    """Mask for display: wesroberts@hotmail.ca -> w***@hotmail.ca (domain kept so the owner
    recognises which inbox, local part hidden)."""
    if not address or "@" not in address:
        return None
    name, _, domain = address.partition("@")
    head = (name[0] + "***") if name else "***"
    return head + "@" + domain


def set_owner_email(db: DbSession, address: str) -> None:
    """Store/replace the owner's 2FA recovery email. Creates the OwnerSecurity row if missing."""
    sec = _owner_security(db)
    if sec is None:
        sec = OwnerSecurity(password_hash="", phones=[], backup_codes=[], audit_log=[], emails=[])
        db.add(sec)
    sec.emails = [{"id": "primary", "label": "email", "address": address.strip()}]
    db.commit()


def issue_code(db: DbSession, sess: AuthSession) -> str:
    """Generate a fresh 6-digit code, store its hash + expiry on the session, return the plaintext
    (for the caller to text). Replaces any prior pending code."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    sess.twofa_code_hash = _hash_code(code)
    sess.twofa_expires_at = datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MINUTES)
    db.commit()
    return code


def _use_backup_code(sec: OwnerSecurity, code: str) -> bool:
    for bc in sec.backup_codes or []:
        if not bc.get("used") and str(bc.get("code")) == code:
            bc["used"] = True
            return True
    return False


def verify_code(db: DbSession, sess: AuthSession, code: str) -> bool:
    """Verify the SMS code (hash + not expired) OR an unused backup code. On success, mark the
    session 2FA-verified and clear the pending code. Constant-time compare on the SMS code."""
    code = (code or "").strip()
    ok = False
    if code and sess.twofa_code_hash and sess.twofa_expires_at:
        exp = sess.twofa_expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp > datetime.now(timezone.utc) and hmac.compare_digest(_hash_code(code), sess.twofa_code_hash):
            ok = True
    if not ok and code:
        sec = _owner_security(db)
        if sec is not None and _use_backup_code(sec, code):
            flag_modified(sec, "backup_codes")
            ok = True
    if ok:
        sess.owner_2fa_verified = True
        sess.twofa_code_hash = None
        sess.twofa_expires_at = None
    db.commit()
    return ok
