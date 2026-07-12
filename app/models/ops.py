"""Operational tail — user-authored records the field/office tools produced only in
localStorage:

- **FollowupReview** (`ij_reviews_v1`) — the §11 follow-up-reviews tool: who to ask for a
  Google review after a completed job, and whether it's been sent/skipped. Upsert by the
  prototype's `id`; the variable record is kept verbatim with a few columns lifted for
  querying. (NiceJob retired — this is the in-app replacement.)
- **UsageEvent** (`ij_usage_v1`) — the consumables used/restock ledger (blades, bags, oil…).
  Append-only; deduped by (item, timestamp, type).
- **PrecheckLog** (`ij_precheck_v1`) — the hands-on crew's morning truck walk-around, one row
  per (brand, truck, date). The parallel to the bin driver's walk-around (stored in
  `bin_driver_day`); flagged items already raise `ij_fixes_v1` defect flags — this keeps the
  full inspection record.
- **PoChase** (`ij_po_needed_v1`) — property-management PO#s to chase before invoicing (PM /
  municipal net-30 jobs need a PO#). Created by the booking, chased in the hubs. Upsert by the
  prototype's `id`; the prototype's demo sample is suppressed by injecting `ij_po_seeded_v1`.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BrandScopedMixin, TimestampMixin, UUIDPkMixin


class FollowupReview(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    __tablename__ = "followup_review"
    __table_args__ = (UniqueConstraint("brand", "source_id", name="uq_review_brand_source"),)

    source_id: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    account: Mapped[str | None] = mapped_column(String(30), nullable=True)     # residential | commercial | property_mgmt
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)       # resolved so we can actually send
    review_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    skipped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # dedup: don't re-send
    sent_to: Mapped[str | None] = mapped_column(String(40), nullable=True)     # the number it went to
    doc: Mapped[dict] = mapped_column(JSONB, nullable=False)   # verbatim review record


class UsageEvent(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    __tablename__ = "usage_event"
    __table_args__ = (UniqueConstraint("brand", "item_id", "at_iso", "type", name="uq_usage_brand_item_at_type"),)

    item_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    item_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    type: Mapped[str | None] = mapped_column(String(20), nullable=True)   # used | restock
    at_iso: Mapped[str] = mapped_column(String(40), nullable=False)       # source ISO timestamp


class PrecheckLog(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    __tablename__ = "precheck_log"
    __table_args__ = (UniqueConstraint("brand", "truck", "check_date", name="uq_precheck_brand_truck_date"),)

    truck: Mapped[str] = mapped_column(String(60), nullable=False)
    check_date: Mapped[date] = mapped_column(Date, nullable=False)
    who: Mapped[str | None] = mapped_column(String(120), nullable=True)
    logged_when: Mapped[str | None] = mapped_column(String(20), nullable=True)
    flagged: Mapped[int | None] = mapped_column(Integer, nullable=True)
    items: Mapped[list] = mapped_column(JSONB, nullable=False)   # [{id,label,status,note}]


class PoChase(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    __tablename__ = "po_chase"
    __table_args__ = (UniqueConstraint("brand", "source_id", name="uq_po_brand_source"),)

    source_id: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)   # needed|requested|ready
    total: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    doc: Mapped[dict] = mapped_column(JSONB, nullable=False)   # verbatim PO-chase record
