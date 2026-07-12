"""Follow-up reviews API (§11). Send the Google-review ask (crew at job-end + the manager
board) and list who's been asked vs not — residential AND commercial. Deduped so no
customer is asked twice.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session as DbSession

from app.api.deps import active_brand_for, get_current_employee
from app.auth.guards import is_owner
from app.db.session import get_db
from app.models.employee import Employee
from app.models.ops import FollowupReview
from app.reviews import service

router = APIRouter(prefix="/reviews", tags=["reviews"])


class SendReviewIn(BaseModel):
    source_id: str | None = None
    name: str | None = None
    phone: str | None = None
    account: str | None = None   # residential | commercial | property_mgmt
    crew: str | None = None
    force: bool = False          # override the dedup (explicit re-send)


@router.post("/send")
def send(body: SendReviewIn, request: Request, db: DbSession = Depends(get_db),
         emp: Employee = Depends(get_current_employee)) -> dict:
    """Send the review ask to a customer (any signed-in crew/manager). Resolves the phone
    (explicit → the record → a unique name match) and dedups. Dry-run until Twilio creds."""
    if not (body.source_id or body.name):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Provide source_id or name")
    brand = active_brand_for(request, emp)
    review = service.get_or_create(db, brand, source_id=body.source_id, name=body.name,
                                   phone=body.phone, account=body.account, crew=body.crew)
    return service.send_review(db, brand, review, phone=body.phone, crew=body.crew, force=body.force)


@router.get("")
def list_reviews(request: Request, only: str = "all", db: DbSession = Depends(get_db),
                 emp: Employee = Depends(get_current_employee)) -> dict:
    """The follow-up-reviews board (owner/manager): who's been asked (✓) vs pending, res +
    commercial. `only=pending|sent|all`."""
    if not (is_owner(emp) or "manager" in (emp.access or [])):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Manager/owner only")
    brand = active_brand_for(request, emp)
    q = select(FollowupReview).where(FollowupReview.brand == brand)
    if only == "pending":
        q = q.where(FollowupReview.review_sent.is_(False), FollowupReview.skipped.is_(False))
    elif only == "sent":
        q = q.where(FollowupReview.review_sent.is_(True))
    rows = db.scalars(q.order_by(desc(FollowupReview.created_at)).limit(500)).all()
    items = [{
        "source_id": r.source_id, "name": r.name, "account": r.account,
        "has_phone": bool(r.phone), "sent": r.review_sent, "skipped": r.skipped,
        "sent_at": r.sent_at.isoformat() if r.sent_at else None,
        "crew": (r.doc or {}).get("crew"), "done_date": (r.doc or {}).get("doneDate"),
    } for r in rows]
    return {
        "brand": brand.value,
        "counts": {"pending": sum(1 for i in items if not i["sent"] and not i["skipped"]),
                   "sent": sum(1 for i in items if i["sent"]), "total": len(items)},
        "reviews": items,
    }
