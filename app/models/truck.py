"""Dispatch trucks (`ij_fleet_v1`) + per-truck notification prefs (`ij_truck_alerts_v1`).

Scope note (open decision #4): this is the DISPATCH-truck roster only. Non-dispatch
equipment (GMC, Bobcat, excavator) and full vehicle/maintenance records are a separate
`vehicle` table in the maintenance domain — kept separate here, matching the prototype.
Colour<->truck mapping lives in `colour_map.assigned_truck` (manager-set), not here.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BrandScopedMixin, TimestampMixin, UUIDPkMixin
from app.db.types import truck_kind_enum
from app.models.enums import TruckKind


class Truck(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    __tablename__ = "truck"
    __table_args__ = (UniqueConstraint("brand", "num", name="uq_truck_brand_num"),)

    num: Mapped[str] = mapped_column(String(20), nullable=False)          # "3".."7", bin-truck label
    lead: Mapped[str | None] = mapped_column(String(120), nullable=True)  # crew lead (manager-set; never hardcoded)
    kind: Mapped[TruckKind | None] = mapped_column(truck_kind_enum, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class TruckAlertPref(Base, UUIDPkMixin, TimestampMixin):
    """1:1 with a truck. Absence of a row = all on. `reassign` is the scheduling-spec
    reassignment-notification toggle."""
    __tablename__ = "truck_alert_pref"

    truck_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("truck.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    reassign: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    swap: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    weigh: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
