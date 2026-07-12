"""Square (payment links) + Dropbox (job-photo filing) endpoints. Both creds-gated —
they return dry-run placeholders until creds are in `.env`. Square NEVER charges (§2/§3);
Dropbox writes ONLY under the configured TEST root (§2/§4).
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.api.deps import active_brand_for, get_current_employee
from app.auth.guards import is_owner
from app.core.config import settings
from app.db.session import get_db
from app.integrations import dropbox_files, square_pay
from app.models.card import CardCharge, StoredCard
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
            "environment": settings.square_environment,
            # public identifiers the Web Payments SDK card field needs on the frontend
            "application_id": settings.square_application_id,
            "location_id": settings.square_location_id}


# ── Square card-on-file (WS3) — store a token, owner-pressed charge ────────────
class SaveCardIn(BaseModel):
    token: str                              # Web Payments SDK token (the raw card never hits us)
    customer_name: str | None = None
    residential_customer_id: str | None = None
    cardholder_name: str | None = None
    auth_note: str | None = None            # the card-on-file authorization the manager captured


@router.post("/square/save-card")
def save_card(body: SaveCardIn, request: Request, db: DbSession = Depends(get_db),
              emp: Employee = Depends(get_current_employee)) -> dict:
    """Store a customer's card on file (manager, at bin booking). The card is tokenized by
    Square's own field — we receive only a token and save the Square customer/card ids +
    brand/last4. NEVER the card number/CVV. Dry-run until Square creds."""
    _manager_or_owner(emp)
    brand = active_brand_for(request, emp)
    if not square_pay.is_configured():
        return {"saved": False, "dry_run": True}
    parts = (body.customer_name or "").strip().split(None, 1)
    given, family = (parts[0] if parts else None), (parts[1] if len(parts) > 1 else None)
    try:
        cust = square_pay.create_customer(given_name=given, family_name=family)
        card = square_pay.save_card_on_file(
            source_token=body.token, customer_id=cust["customer_id"],
            cardholder_name=body.cardholder_name or body.customer_name)
    except square_pay.SquareError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Card not saved: {e}")
    rc_id = None
    if body.residential_customer_id:
        try:
            rc_id = uuid.UUID(str(body.residential_customer_id))
        except ValueError:
            rc_id = None
    sc = StoredCard(
        brand=brand, residential_customer_id=rc_id, customer_name=body.customer_name,
        square_customer_id=cust["customer_id"], square_card_id=card["card_id"],
        card_brand=card.get("brand"), card_last4=card.get("last4"),
        exp_month=card.get("exp_month"), exp_year=card.get("exp_year"),
        authorized_by=emp.name, auth_note=body.auth_note, active=True)
    db.add(sc)
    db.commit()
    return {"saved": True, "id": str(sc.id), "brand": sc.card_brand, "last4": sc.card_last4}


@router.get("/square/card-on-file")
def card_on_file(customer_name: str, request: Request, db: DbSession = Depends(get_db),
                 emp: Employee = Depends(get_current_employee)) -> dict:
    """Does this customer have a card on file? (owner/manager) — drives showing the charge button."""
    _manager_or_owner(emp)
    brand = active_brand_for(request, emp)
    sc = db.scalar(select(StoredCard).where(
        StoredCard.brand == brand, StoredCard.customer_name == customer_name,
        StoredCard.active.is_(True)).order_by(StoredCard.created_at.desc()))
    if sc is None:
        return {"on_file": False}
    return {"on_file": True, "id": str(sc.id), "brand": sc.card_brand, "last4": sc.card_last4}


class ChargeCardIn(BaseModel):
    stored_card_id: str | None = None       # our StoredCard id (preferred)
    customer_name: str | None = None        # else the active card for this customer
    amount: Decimal                         # invoice total + 2.4% (already computed)
    job_id: str | None = None               # idempotency key -> one charge per bin job
    note: str | None = None


@router.post("/square/charge-card-on-file")
def charge_card(body: ChargeCardIn, request: Request, db: DbSession = Depends(get_db),
                emp: Employee = Depends(get_current_employee)) -> dict:
    """Charge a customer's saved card (OWNER ONLY — the manager cannot). THE one charge action,
    fired only from an owner tap (never automatic). Idempotent per job. Records a CardCharge
    audit row either way. On decline, returns a reason and leaves the job unpaid."""
    if not is_owner(emp):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Owner only")
    brand = active_brand_for(request, emp)
    q = select(StoredCard).where(StoredCard.brand == brand, StoredCard.active.is_(True))
    if body.stored_card_id:
        try:
            q = q.where(StoredCard.id == uuid.UUID(str(body.stored_card_id)))
        except ValueError:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Bad stored_card_id")
    elif body.customer_name:
        q = q.where(StoredCard.customer_name == body.customer_name).order_by(StoredCard.created_at.desc())
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Provide stored_card_id or customer_name")
    sc = db.scalar(q)
    if sc is None:
        return {"charged": False, "reason": "no_card_on_file"}
    if not square_pay.is_configured():
        return {"charged": False, "dry_run": True}
    job_uuid = None
    if body.job_id:
        try:
            job_uuid = uuid.UUID(str(body.job_id))
        except ValueError:
            job_uuid = None
    cents = int(round(float(body.amount) * 100))
    idem = ("cof-" + str(body.job_id or sc.id)).replace(":", "-")[:45]
    try:
        res = square_pay.charge_card_on_file(
            card_id=sc.square_card_id, customer_id=sc.square_customer_id,
            amount=body.amount, note=body.note, idempotency_key=idem)
    except square_pay.SquareError as e:
        db.add(CardCharge(brand=brand, stored_card_id=sc.id, job_id=job_uuid, amount_cents=cents,
                          status="DECLINED", note=str(e)[:500], created_by=emp.name))
        db.commit()
        return {"charged": False, "reason": str(e), "brand": sc.card_brand, "last4": sc.card_last4}
    db.add(CardCharge(brand=brand, stored_card_id=sc.id, job_id=job_uuid,
                      amount_cents=res.get("amount_cents") or cents, square_payment_id=res.get("payment_id"),
                      status=res.get("status"), note=body.note, created_by=emp.name))
    db.commit()
    return {"charged": res.get("status") == "COMPLETED", "status": res.get("status"),
            "payment_id": res.get("payment_id"), "amount_cents": res.get("amount_cents"),
            "brand": sc.card_brand, "last4": sc.card_last4}


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
