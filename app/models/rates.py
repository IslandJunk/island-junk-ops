"""Pricing: rate card, area surcharges (+ waiver log), and the disposal cost model
(facilities + materials + rate history). One `rate_card` row per brand mirrors the
prototype's `ij_rates_v1` blob (scalars as columns; price tables/lists as JSONB).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BrandScopedMixin, TimestampMixin, UUIDPkMixin
from app.db.types import disposal_role_enum
from app.models.enums import DisposalRole


class RateCard(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    """Single row per brand."""
    __tablename__ = "rate_card"
    __table_args__ = (UniqueConstraint("brand", name="uq_rate_card_brand"),)

    labour_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("125"))
    demo_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("165"))
    crew_extra_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("62.5"))
    recycle_charge: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("25"))
    diversion_surcharge: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("45"))
    diversion_report: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("100"))
    gst_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("5"))
    card_fee_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("2.4"))

    # Sub-structures (faithful to ij_rates_v1); edited from the UI, rippled to forms.
    parking: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    travel: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    residential_loads: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    commercial_loads: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    residential_min: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    commercial_included_min: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    specials: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    ppe: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    bin_rates: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    yard_waste: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class AreaSurcharge(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    """Per-area hand-load and/or bin surcharge; auto-applied on address match,
    one-tap waivable (logged). Adopts the richer Nanaimo shape for both brands."""
    __tablename__ = "area_surcharge"

    area_name: Mapped[str] = mapped_column(String(120), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    hand_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    bin_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    # Victoria bins carry a separate roofing surcharge (rate sheet `roofingSurcharges`);
    # only Sooke differs from the regular bin surcharge, but the column keeps both exact.
    roofing_bin_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    is_base: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class SurchargeWaiver(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    """Logged when a manager one-tap skips a surcharge (truck already headed that way)."""
    __tablename__ = "surcharge_waiver"

    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job.id", ondelete="CASCADE"), nullable=True, index=True
    )
    area_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("area_surcharge.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str | None] = mapped_column(String(20), nullable=True)   # hand | bin
    waived_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DisposalFacility(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    """Where material goes + who pays (`ij_rates_v1.facilities[]`)."""
    __tablename__ = "disposal_facility"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[DisposalRole] = mapped_column(disposal_role_enum, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class DisposalMaterial(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    """Materials registry — customer charge (`price`) vs our cost (`cost`)."""
    __tablename__ = "disposal_material"

    m: Mapped[str] = mapped_column(String(120), nullable=False)
    facility_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("disposal_facility.id", ondelete="SET NULL"), nullable=True
    )
    cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)   # blank = computed from streams
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class DisposalRateHistory(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    """Effective-dated history for disposal rates (§9 requires history; prototype had none)."""
    __tablename__ = "disposal_rate_history"

    material_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("disposal_material.id", ondelete="SET NULL"), nullable=True, index=True
    )
    m: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    changed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
