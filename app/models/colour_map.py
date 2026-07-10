"""Colour → truck/status map (`ij_colourmap_v1`), brand-scoped and editable.

This is the authoritative palette the app uses to compute a job's Google colorId.
Truck + status are stored on the job as separate fields; this table says what each
colour *means*. `assigned_truck` is a truck number/label (string, manager-set) to
match the prototype's `assign: {colourKey: truckNum}` — it does NOT FK a vehicle
table yet (that unification is still an open decision).

Decisions banked here: Flamingo = STATUS only; bin truck = Graphite/Blueberry.
"""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BrandScopedMixin, TimestampMixin, UUIDPkMixin
from app.db.types import colour_kind_enum
from app.models.enums import ColourKind


class ColourMap(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    __tablename__ = "colour_map"
    __table_args__ = (UniqueConstraint("brand", "key", name="uq_colour_map_brand_key"),)

    key: Mapped[str] = mapped_column(String(40), nullable=False)          # e.g. "blueberry"
    name: Mapped[str] = mapped_column(String(60), nullable=False)         # display label
    google_color_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1..11 classic; null for custom
    hex: Mapped[str | None] = mapped_column(String(7), nullable=True)
    kind: Mapped[ColourKind] = mapped_column(colour_kind_enum, nullable=False)

    # For status colours: what it signals (e.g. "Residential bin — CC unpaid").
    status_meaning: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # For assignable colours currently mapped to a truck (manager-set); string, not FK yet.
    assigned_truck: Mapped[str | None] = mapped_column(String(20), nullable=True)

    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # sage + all status colours are locked from truck assignment.
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
