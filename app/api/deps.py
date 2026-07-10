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


def require_manager(emp: Employee = Depends(get_current_employee)) -> Employee:
    """Gate for manager-only actions (e.g. booking). Owner always passes."""
    if not (is_owner(emp) or "manager" in (emp.access or [])):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Manager access required")
    return emp
