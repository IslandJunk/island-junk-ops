"""Disposal margins — owner-facing read of the computed disposal cost model
(customer charge vs our cost per processed load). Read-only; no charging (guardrail §2)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as DbSession

from app.api.deps import active_brand_for, get_current_employee
from app.auth.guards import is_owner
from app.db.session import get_db
from app.models.employee import Employee
from app.yard.disposal import load_margins

router = APIRouter(prefix="/disposal", tags=["disposal"])


@router.get("/margins")
def margins(request: Request, db: DbSession = Depends(get_db),
            emp: Employee = Depends(get_current_employee)) -> dict:
    """Every processed load's disposal margin for the caller's active brand (owner-only)."""
    if not is_owner(emp):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Owner access required")
    return load_margins(db, active_brand_for(request, emp))
