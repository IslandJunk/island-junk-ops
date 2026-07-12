"""Follow-up review sending (§11). Sends the Google-review ask from the updates line and
tracks who it's gone to, so the same customer is never asked twice — the two dedup gates:
  1. this review record is already sent (`review_sent`), and
  2. this phone got a review recently (any record with a matching `sent_to`).
Both are skippable with `force=True` (an explicit re-send).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models.enums import Brand
from app.models.ops import FollowupReview
from app.sms import routing, service as sms_service, templates

RESEND_GUARD_DAYS = 60   # don't re-ask the same number within this window


def get_or_create(db: DbSession, brand: Brand, *, source_id: str | None, name: str | None,
                  phone: str | None, account: str | None, crew: str | None) -> FollowupReview:
    """Find the review record by source_id, else create one (e.g. the crew sending straight
    from a job that has no prior review row)."""
    row = None
    if source_id:
        row = db.scalar(select(FollowupReview).where(
            FollowupReview.brand == brand, FollowupReview.source_id == str(source_id)))
    if row is None:
        sid = str(source_id) if source_id else "rv_" + re.sub(r"[^a-z0-9]+", "_", (name or "").lower())[:40]
        row = db.scalar(select(FollowupReview).where(
            FollowupReview.brand == brand, FollowupReview.source_id == sid))
        if row is None:
            row = FollowupReview(brand=brand, source_id=sid, doc={})
            db.add(row)
    if name:
        row.name = name
    if account:
        row.account = account
    if phone:
        row.phone = phone.strip()
    if crew and isinstance(row.doc, dict):
        row.doc = {**row.doc, "crew": crew}
    db.flush()
    return row


def _recent_review_to(db: DbSession, brand: Brand, phone: str) -> FollowupReview | None:
    want = routing.digits10(phone)
    if not want:
        return None
    cutoff = datetime.now(timezone.utc) - timedelta(days=RESEND_GUARD_DAYS)
    for r in db.scalars(select(FollowupReview).where(
            FollowupReview.brand == brand, FollowupReview.sent_at.isnot(None), FollowupReview.sent_at >= cutoff)):
        if routing.digits10(r.sent_to or "") == want:
            return r
    return None


def send_review(db: DbSession, brand: Brand, review: FollowupReview, *,
                phone: str | None = None, crew: str | None = None, force: bool = False) -> dict:
    """Send the review ask + mark it sent. Deduped unless force=True."""
    to = (phone or review.phone or "").strip()
    if not to:
        return {"sent": False, "reason": "no_phone", "name": review.name}
    if not force:
        if review.review_sent:
            return {"sent": False, "reason": "already_sent", "name": review.name,
                    "at": review.sent_at.isoformat() if review.sent_at else None}
        dup = _recent_review_to(db, brand, to)
        if dup is not None:
            return {"sent": False, "reason": "customer_already_asked", "name": review.name,
                    "at": dup.sent_at.isoformat() if dup.sent_at else None}
    crew = crew or (review.doc or {}).get("crew")
    body = templates.render(db, brand, "review", {"name": review.name, "crew": crew})
    res = sms_service.send(db, brand=brand, to=to, body=body, kind="review")
    review.review_sent = True
    review.sent_at = datetime.now(timezone.utc)
    review.sent_to = to
    db.commit()
    return {"sent": bool(res.get("sent")), "to": to, "body": body, "name": review.name,
            "dry_run": res.get("dry_run"), "skipped": res.get("skipped")}
