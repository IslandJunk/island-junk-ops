"""Ready-to-invoice queue — owner-facing read (§11). Surfaces completed jobs ready to
bill; never invoices or charges (guardrail §2)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as DbSession

from app.api.deps import active_brand_for, get_current_employee
from app.auth.guards import is_owner
from app.db.session import get_db
from app.invoicing.service import invoice_queue
from app.models.employee import Employee

router = APIRouter(prefix="/invoice-queue", tags=["invoicing"])


@router.get("")
def queue(request: Request, db: DbSession = Depends(get_db),
          emp: Employee = Depends(get_current_employee)) -> dict:
    """What's ready for the owner to invoice + roll-off bins overdue to bill (owner-only)."""
    if not is_owner(emp):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Owner access required")
    return invoice_queue(db, active_brand_for(request, emp))
