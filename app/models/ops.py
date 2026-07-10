"""Operational tail — user-authored records the field/office tools produced only in
localStorage:

- **FollowupReview** (`ij_reviews_v1`) — the §11 follow-up-reviews tool: who to ask for a
  Google review after a completed job, and whether it's been sent/skipped. Upsert by the
  prototype's `id`; the variable record is kept verbatim with a few columns lifted for
  querying. (NiceJob retired — this is the in-app replacement.)
- **UsageEvent** (`ij_usage_v1`) — the consumables used/restock ledger (blades, bags, oil…).
  Append-only; deduped by (item, timestamp, type).

(PO-chase `ij_po_needed_v1` deferred — its demo seed is guarded by a separate
`ij_po_seeded_v1` flag, so it needs seed-guard handling before it can sync cleanly.)
"""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BrandScopedMixin, TimestampMixin, UUIDPkMixin


class FollowupReview(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    __tablename__ = "followup_review"
    __table_args__ = (UniqueConstraint("brand", "source_id", name="uq_review_brand_source"),)

    source_id: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    review_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    skipped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    doc: Mapped[dict] = mapped_column(JSONB, nullable=False)   # verbatim review record


class UsageEvent(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    __tablename__ = "usage_event"
    __table_args__ = (UniqueConstraint("brand", "item_id", "at_iso", "type", name="uq_usage_brand_item_at_type"),)

    item_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    item_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    type: Mapped[str | None] = mapped_column(String(20), nullable=True)   # used | restock
    at_iso: Mapped[str] = mapped_column(String(40), nullable=False)       # source ISO timestamp
