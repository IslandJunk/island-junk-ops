"""Yard processing record — the rich per-load close-out the crew fills at the scale
(stream %, waste class, extras, axle weights). The prototype keeps this in memory, so
it's saved via a dedicated endpoint (not the generic localStorage sync). Feeds the
disposal cost model. Upserted by (brand, code, processed_date).
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BrandScopedMixin, TimestampMixin, UUIDPkMixin


class YardProcessing(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    __tablename__ = "yard_processing"
    __table_args__ = (UniqueConstraint("brand", "code", "processed_date", name="uq_yardproc_brand_code_date"),)

    code: Mapped[str] = mapped_column(String(30), nullable=False)      # bin code or HL-T4 (hand load)
    ref: Mapped[str | None] = mapped_column(String(60), nullable=True)
    type: Mapped[str | None] = mapped_column(String(20), nullable=True)   # bin | handload
    size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    roofing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    customer: Mapped[str | None] = mapped_column(String(180), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    town: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pickup_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    truck: Mapped[str | None] = mapped_column(String(60), nullable=True)
    hq_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pick_date: Mapped[str | None] = mapped_column(String(20), nullable=True)

    crew: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    crew_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    gross_f: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    gross_r: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    tare_f: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    tare_r: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    gross: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    tare: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    waste_class: Mapped[str | None] = mapped_column(String(120), nullable=True)
    dump_fee: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    pct: Mapped[dict | None] = mapped_column(JSONB, nullable=True)          # {junk,wood,drywall,concrete,metal,recycle}
    extras: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    custom_extras: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    process_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    weighed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    processed_clock: Mapped[str | None] = mapped_column(String(20), nullable=True)
    processed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    photos: Mapped[list | None] = mapped_column(JSONB, nullable=True)
