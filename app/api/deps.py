"""Request dependencies — resolve the current employee from a signed session cookie."""
from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, Request, status
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy.orm import Session as DbSession

from app.auth.guards import is_owner
from app.auth.service import get_active_session
from app.core.config import settings
from app.db.session import get_db
from app.models.employee import Employee

COOKIE_NAME = "ij_session"
_serializer = URLSafeSerializer(settings.session_secret, salt="ij-session")


def make_cookie(session_id: uuid.UUID) -> str:
    return _serializer.dumps(str(session_id))


def _read_cookie(raw: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(_serializer.loads(raw))
    except (BadSignature, ValueError, TypeError):
        return None


def get_current_employee(request: Request, db: DbSession = Depends(get_db)) -> Employee:
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    session_id = _read_cookie(raw)
    if session_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")
    sess = get_active_session(db, session_id)
    if sess is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session ended")
    emp = db.get(Employee, sess.employee_id)
    if emp is None or not emp.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account inactive")
    request.state.session = sess  # let handlers read active_brand
    return emp


def active_brand_for(request: Request, emp: Employee) -> "Brand":
    """The brand a signed-in user is currently working in: the owner follows the session's
    switchable `active_brand`; crew are locked to their own brand. Defaults to Victoria.
    (Brand-scoped reads/actions resolve here; the owner-only guard stays separate.)"""
    from app.models.enums import Brand
    sess = getattr(request.state, "session", None)
    if is_owner(emp) and sess is not None and sess.active_brand is not None:
        return sess.active_brand
    return emp.brand or Brand.victoria


def get_active_brand(request: Request, emp: Employee = Depends(get_current_employee)) -> "Brand":
    """Dependency form of `active_brand_for` for endpoints that just need the working brand."""
    return active_brand_for(request, emp)


def optional_brand(request: Request, db: DbSession = Depends(get_db)) -> "Brand":
    """Resolve the working brand for a SERVED PAGE without requiring auth: read the session
    cookie if present (owner -> active_brand, crew -> their brand), else default Victoria.
    Never raises — a logged-out visitor (the login screen) just gets Victoria."""
    from app.models.enums import Brand
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        return Brand.victoria
    session_id = _read_cookie(raw)
    if session_id is None:
        return Brand.victoria
    sess = get_active_session(db, session_id)
    if sess is None:
        return Brand.victoria
    emp = db.get(Employee, sess.employee_id)
    if emp is None or not emp.active:
        return Brand.victoria
    if is_owner(emp) and sess.active_brand is not None:
        return sess.active_brand
    return emp.brand or Brand.victoria


def require_manager(emp: Employee = Depends(get_current_employee)) -> Employee:
    """Gate for manager-only actions (e.g. booking). Owner always passes."""
    if not (is_owner(emp) or "manager" in (emp.access or [])):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Manager access required")
    return emp
