"""Login + session lifecycle.

Scope note: this implements PIN login, brand-scoped candidate matching, and
session create/lookup/end. The full login/sessions spec (device-type logout
rules, overnight safety-net, continuous autosave) layers on top of these tables
and is a later pass — TODOs mark the seams.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.auth.security import normalize_pin, verify_pin
from app.models.employee import Employee
from app.models.enums import Brand
from app.models.session import Device, Session as AuthSession


def authenticate(db: DbSession, *, pin: str, brand: Brand | None) -> Employee | None:
    """Return the employee whose PIN matches, scoped to `brand`.

    Crew/managers are locked to one brand; the owner (brand = NULL) matches on any
    device. PINs should be unique within a brand (enforced at seed/admin time);
    first active match wins.
    """
    pin = normalize_pin(pin)
    candidates = db.scalars(select(Employee).where(Employee.active.is_(True))).all()
    for emp in candidates:
        if emp.brand is not None and brand is not None and emp.brand != brand:
            continue  # crew locked to a different brand
        if verify_pin(pin, emp.pin_hash):
            return emp
    return None


def create_session(
    db: DbSession, *, employee: Employee, device: Device | None = None,
    active_brand: Brand | None = None,
) -> AuthSession:
    sess = AuthSession(
        employee_id=employee.id,
        device_id=device.id if device else None,
        # Owner may switch brands; locked crew mirror their own brand.
        active_brand=active_brand or employee.brand,
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


def get_active_session(db: DbSession, session_id: uuid.UUID) -> AuthSession | None:
    sess = db.get(AuthSession, session_id)
    if sess is None or sess.ended_at is not None:
        return None
    # TODO(login-spec): apply overnight safety-net (fresh PIN if session spans a
    # prior workday) using device.type + last_seen_at before treating as valid.
    sess.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    return sess


def end_session(db: DbSession, sess: AuthSession) -> None:
    sess.ended_at = datetime.now(timezone.utc)
    db.commit()
