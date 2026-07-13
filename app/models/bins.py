"""Bin asset ledger (`ij_bins_v1`) — unifies the three divergent prototype shapes
(registry `state`, yard write-back, and the driver's non-persisting `status`) into
one table. Natural key `code` = SIZE-NN (e.g. 16-04), unique per brand.

`leased` (11 ROSS bins -> Nanaimo) and `stationed` (long-term at a customer) are
flags, not statuses.
"""
from __future__ import annotations

import uuid
from datetime import date, time
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text, Time, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BrandScopedMixin, TimestampMixin, UUIDPkMixin
from app.db.types import bin_status_enum
from app.models.enums import BinStatus


class Bin(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    __tablename__ = "bin"
    __table_args__ = (UniqueConstraint("brand", "code", name="uq_bin_brand_code"),)

    # Identity / asset attributes
    code: Mapped[str] = mapped_column(String(12), nullable=False)          # "16-04"
    size: Mapped[int] = mapped_column(Integer, nullable=False)             # 8|12|16|20 yd
    lidded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    custom_lid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    leased: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)     # ROSS -> Nanaimo
    stationed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # long-term at a customer
    type: Mapped[str | None] = mapped_column(String(60), nullable=True)   # usual material
    roofing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    condition: Mapped[dict | None] = mapped_column(JSONB, nullable=True)   # {flag, note, photos}
    status: Mapped[BinStatus] = mapped_column(bin_status_enum, nullable=False, default=BinStatus.idle)

    # Assignment / current job
    customer: Mapped[str | None] = mapped_column(String(180), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    town: Mapped[str | None] = mapped_column(String(120), nullable=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job.id", ondelete="SET NULL"), nullable=True
    )

    # Rental reference — BIN-xxxx, minted when the bin goes OUT (dropped/full from a non-out
    # state). It's the QB match key the owner pastes into the invoice PO field, and it rides the
    # bins-out list the pickup picker uses (so drop and pickup share it via this bin/out-period).
    # `rental_group_id` = the internal per-rental id. Both re-mint on the next fresh drop.
    reference_code: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    rental_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Rental / dates
    drop_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    drop_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    pick_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    scheduled_pickup: Mapped[date | None] = mapped_column(Date, nullable=True)
    hq_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    last_dumped: Mapped[date | None] = mapped_column(Date, nullable=True)
    yard_at: Mapped[time | None] = mapped_column(Time, nullable=True)
    base: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    surcharge: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Weigh / disposal
    gross: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    tare: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    gross_f: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    gross_r: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    tare_f: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    tare_r: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    waste_class: Mapped[str | None] = mapped_column(String(120), nullable=True)
    dump_fee: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    fee_split: Mapped[list | None] = mapped_column(JSONB, nullable=True)   # [{job, amt}]
    extra_time: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pickup_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    dump_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sort_junk: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sort_metal: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sort_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    no_sort: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cleared: Mapped[dict | None] = mapped_column(JSONB, nullable=True)     # roofing clear summary

    # Misc
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    photos: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    contact_log: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # overdue-rental chase log
    repair_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    repair_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    repair_at: Mapped[date | None] = mapped_column(Date, nullable=True)
