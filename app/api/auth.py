"""Auth routes: PIN login, logout, and current-user."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from app.api.deps import COOKIE_NAME, get_current_employee, make_cookie
from app.auth import service, twofa
from app.auth.guards import is_owner
from app.core.config import settings
from app.db.session import get_db
from app.models.employee import Employee
from app.models.enums import Brand

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    pin: str
    # On a real device the brand comes from the device registration, not the client.
    # Accepted here for the login flow / owner brand selection.
    brand: Brand | None = None


class EmployeeOut(BaseModel):
    id: str
    name: str
    role: str
    brand: Brand | None
    access: list[str]
    is_owner: bool
    active_brand: Brand | None = None


def _to_out(emp: Employee, active_brand: Brand | None = None) -> EmployeeOut:
    return EmployeeOut(
        id=str(emp.id), name=emp.name, role=emp.role, brand=emp.brand,
        access=list(emp.access or []), is_owner=is_owner(emp), active_brand=active_brand,
    )


@router.post("/login", response_model=EmployeeOut)
def login(body: LoginIn, response: Response, db: DbSession = Depends(get_db)) -> EmployeeOut:
    emp = service.authenticate(db, pin=body.pin, brand=body.brand)
    if emp is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong PIN")
    sess = service.create_session(db, employee=emp, active_brand=body.brand)
    response.set_cookie(COOKIE_NAME, make_cookie(sess.id), httponly=True, samesite="lax")
    return _to_out(emp, sess.active_brand)


@router.post("/logout")
def logout(request: Request, response: Response, db: DbSession = Depends(get_db),
           emp: Employee = Depends(get_current_employee)) -> dict:
    sess = getattr(request.state, "session", None)
    if sess is not None:
        service.end_session(db, sess)
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@router.get("/me", response_model=EmployeeOut)
def me(request: Request, emp: Employee = Depends(get_current_employee)) -> EmployeeOut:
    sess = getattr(request.state, "session", None)
    return _to_out(emp, sess.active_brand if sess else None)


class BrandIn(BaseModel):
    brand: Brand


@router.post("/brand", response_model=EmployeeOut)
def set_active_brand(body: BrandIn, request: Request, db: DbSession = Depends(get_db),
                     emp: Employee = Depends(get_current_employee)) -> EmployeeOut:
    """Owner switches the workspace (§3): everything the owner sees/edits after this follows
    the new brand. Owner-only — crew are locked to their brand (never switch). The switch
    persists on the session; the next page load serves the new brand's data."""
    if not is_owner(emp):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the owner can switch workspace")
    sess = getattr(request.state, "session", None)
    if sess is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No active session")
    sess.active_brand = body.brand
    db.commit()
    return _to_out(emp, sess.active_brand)


# ── Owner SMS 2FA (real second factor for the owner account) ──────────────────
def _owner_session(request: Request, emp: Employee):
    """Owner + an active session — the gate for the 2FA setup/verify endpoints, which must be
    reachable BEFORE the second factor is verified. Sensitive endpoints use require_owner_2fa."""
    if not is_owner(emp):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Owner only")
    sess = getattr(request.state, "session", None)
    if sess is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No active session")
    return sess


@router.get("/2fa/status")
def twofa_status(request: Request, db: DbSession = Depends(get_db),
                 emp: Employee = Depends(get_current_employee)) -> dict:
    sess = _owner_session(request, emp)
    phone = twofa.owner_phone(db)
    email = twofa.owner_email(db)
    return {"verified": bool(sess.owner_2fa_verified),
            "phone_set": bool(phone), "phone_masked": twofa.mask_phone(phone),
            "email_set": bool(email), "email_masked": twofa.mask_email(email),
            "email_channel_ready": settings.is_email_configured}


class PhoneIn(BaseModel):
    number: str


@router.post("/2fa/set-phone")
def twofa_set_phone(body: PhoneIn, request: Request, db: DbSession = Depends(get_db),
                    emp: Employee = Depends(get_current_employee)) -> dict:
    """First-time setup: store the owner's cell for the 2FA code. Owner-only."""
    _owner_session(request, emp)
    digits = "".join(ch for ch in (body.number or "") if ch.isdigit())
    if len(digits) < 10:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Enter a valid phone number")
    twofa.set_owner_phone(db, body.number)
    return {"phone_masked": twofa.mask_phone(body.number)}


class EmailIn(BaseModel):
    address: str


@router.post("/2fa/set-email")
def twofa_set_email(body: EmailIn, request: Request, db: DbSession = Depends(get_db),
                    emp: Employee = Depends(get_current_employee)) -> dict:
    """Store the owner's recovery email — the 2FA code can be sent here as an alternative to
    SMS (e.g. if the phone is lost/unavailable). Owner-only."""
    _owner_session(request, emp)
    addr = (body.address or "").strip()
    domain = addr.split("@")[-1] if "@" in addr else ""
    if "@" not in addr or "." not in domain or len(addr) < 5:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Enter a valid email address")
    twofa.set_owner_email(db, addr)
    return {"email_masked": twofa.mask_email(addr)}


class RequestIn(BaseModel):
    channel: str = "sms"   # "sms" (default) | "email"


@router.post("/2fa/request")
def twofa_request(request: Request, db: DbSession = Depends(get_db),
                  emp: Employee = Depends(get_current_employee),
                  body: RequestIn | None = None) -> dict:
    """Send a fresh 6-digit code to the owner — by SMS (default, from the send-only updates
    line, opt-out bypassed since it's a security code) or by EMAIL (recovery channel, e.g. if
    the phone is lost). The code is stored hashed with a 10-minute expiry; verification
    (/2fa/verify) is identical for both channels."""
    sess = _owner_session(request, emp)
    channel = (body.channel if body else "sms") or "sms"

    if channel == "email":
        email = twofa.owner_email(db)
        if not email:
            raise HTTPException(status.HTTP_409_CONFLICT, "Add a recovery email first")
        if not settings.is_email_configured:
            # Bail BEFORE issuing a code so any code already texted stays valid.
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                                "Email isn't set up yet - use your texted code.")
        code = twofa.issue_code(db, sess)
        text = (f"Your Island Junk owner sign-in code is {code} (valid 10 minutes).\n\n"
                f"If you didn't try to sign in, you can ignore this email.")
        try:
            from app.integrations.email_send import send_email
            send_email(email, "Island Junk owner login code", text)
        except Exception:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                                "Couldn't send the email code - try again, or use SMS.")
        return {"sent": True, "channel": "email", "to_masked": twofa.mask_email(email)}

    # Default channel: SMS.
    phone = twofa.owner_phone(db)
    if not phone:
        raise HTTPException(status.HTTP_409_CONFLICT, "Add your phone first")
    code = twofa.issue_code(db, sess)
    text = f"Island Junk owner login code: {code} (valid 10 min). Not you? Ignore this."
    try:
        from app.sms import service as sms_service
        sms_service.send(db, brand=None, to=phone, body=text, kind="owner_2fa", respect_opt_out=False)
    except Exception:
        pass  # code is stored; delivery is best-effort (owner can retry or switch channel)
    return {"sent": True, "channel": "sms", "to_masked": twofa.mask_phone(phone)}


class CodeIn(BaseModel):
    code: str


@router.post("/2fa/verify")
def twofa_verify(body: CodeIn, request: Request, db: DbSession = Depends(get_db),
                 emp: Employee = Depends(get_current_employee)) -> dict:
    """Verify the texted code (or a backup code). On success the session is 2FA-verified and the
    Owner Hub + sensitive owner actions unlock for that session."""
    sess = _owner_session(request, emp)
    if not twofa.verify_code(db, sess, body.code):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired code")
    return {"verified": True}
