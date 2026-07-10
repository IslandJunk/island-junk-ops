"""Auth routes: PIN login, logout, and current-user."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from app.api.deps import COOKIE_NAME, get_current_employee, make_cookie
from app.auth import service
from app.auth.guards import is_owner
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
