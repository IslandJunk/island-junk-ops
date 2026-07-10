"""Square (payment links) + Dropbox (job-photo filing) endpoints. Both creds-gated —
they return dry-run placeholders until creds are in `.env`. Square NEVER charges (§2/§3);
Dropbox writes ONLY under the configured TEST root (§2/§4).
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_employee
from app.auth.guards import is_owner
from app.core.config import settings
from app.db.session import get_db
from app.integrations import dropbox_files, square_pay
from app.models.employee import Employee

router = APIRouter(tags=["integrations"])


def _manager_or_owner(emp: Employee) -> None:
    if not (is_owner(emp) or "manager" in (emp.access or [])):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Manager/owner only")


# ── Square: payment links (surface only, never charge) ────────────────────────
class PaymentLinkIn(BaseModel):
    amount: Decimal
    name: str
    note: str | None = None


@router.post("/square/payment-link")
def payment_link(body: PaymentLinkIn, db: DbSession = Depends(get_db),
                 emp: Employee = Depends(get_current_employee)) -> dict:
    """Create a Square pay-by-card link for a job amount (owner/manager). Never charges —
    the customer completes payment via the returned URL. Dry-run until Square creds are set."""
    _manager_or_owner(emp)
    return square_pay.create_payment_link(amount=body.amount, name=body.name, note=body.note)


@router.get("/square/status")
def square_status(emp: Employee = Depends(get_current_employee)) -> dict:
    _manager_or_owner(emp)
    return {"configured": square_pay.is_configured(),
            "mode": "live" if square_pay.is_configured() else "dry_run",
            "environment": settings.square_environment}


# ── Dropbox: auto-file job photos (TEST folder first) ─────────────────────────
class JobPhotoIn(BaseModel):
    job_ref: str
    filename: str
    data_url: str      # data:image/...;base64,...  (from the crew form)


@router.post("/dropbox/job-photo")
def dropbox_job_photo(body: JobPhotoIn, emp: Employee = Depends(get_current_employee)) -> dict:
    """File one job photo into the job's Dropbox folder (any signed-in crew). Writes only
    under the configured TEST root; dry-run until Dropbox creds are set."""
    try:
        return dropbox_files.upload_job_photo(
            job_ref=body.job_ref, filename=body.filename, data_url=body.data_url)
    except dropbox_files.DropboxGuardError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.get("/dropbox/status")
def dropbox_status(emp: Employee = Depends(get_current_employee)) -> dict:
    _manager_or_owner(emp)
    return {"configured": dropbox_files.is_configured(),
            "mode": "live" if dropbox_files.is_configured() else "dry_run",
            "root": settings.dropbox_root}
