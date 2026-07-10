"""Weigh log (`ij_weighlog_v1`) — append-only truck+bin axle-weight events from the
yard. `source_at` is the prototype's ms-epoch timestamp; (brand, source_at, bin) is
unique so re-syncs don't duplicate an event.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, Date, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BrandScopedMixin, TimestampMixin, UUIDPkMixin


class WeighLog(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    __tablename__ = "weigh_log"
    __table_args__ = (UniqueConstraint("brand", "source_at", "bin", name="uq_weigh_brand_at_bin"),)

    source_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # ms epoch
    weigh_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    weigh_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    who: Mapped[str | None] = mapped_column(String(120), nullable=True)
    truck: Mapped[str | None] = mapped_column(String(60), nullable=True)
    bin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cls: Mapped[str | None] = mapped_column(String(60), nullable=True)      # e.g. "Bin truck"
    source: Mapped[str | None] = mapped_column(String(60), nullable=True)   # e.g. "weighoff"
    front_kg: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    rear_kg: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    total_kg: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
