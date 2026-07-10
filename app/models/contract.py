"""Contracts / custom customers (`ij_contracts_v1`). Built-in contracts (Oak Bay,
Saanich, ...) stay runtime constants; user-added/overlaid contracts live here.
The per-customer rate profile (`rate_customer`) is folded in as `rates` JSONB.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BrandScopedMixin, TimestampMixin, UUIDPkMixin
from app.db.types import contract_pricing_enum
from app.models.enums import ContractPricing


class Contract(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    __tablename__ = "contract"
    __table_args__ = (UniqueConstraint("brand", "key", name="uq_contract_brand_key"),)

    key: Mapped[str] = mapped_column(String(80), nullable=False)          # slug
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    short: Mapped[str | None] = mapped_column(String(120), nullable=True)

    pricing: Mapped[ContractPricing] = mapped_column(contract_pricing_enum, nullable=False)
    rate_key: Mapped[str | None] = mapped_column(String(80), nullable=True)

    divisions: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)   # department picker
    route_divs: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)  # force Route Builder
    div_addable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    extra: Mapped[str | None] = mapped_column(String(20), nullable=True)  # scale|location|trail|property
    bin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    po_req: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    site_log: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    shots: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)  # required photos
    terms: Mapped[str | None] = mapped_column(Text, nullable=True)

    rates: Mapped[list | None] = mapped_column(JSONB, nullable=True)      # [{label,val,unit}] rate profile
    flat: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    flat_unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    properties: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # flatmonthly stops
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
