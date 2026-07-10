"""Device + Session (login/sessions spec).

The prototype only had a coarse 16h timer; the real model is built here.
Key rule: **no idle timeout ever.** Logout behaviour is driven solely by
`device.type` (shared_tablet vs personal_phone), plus an overnight safety-net
that forces a fresh PIN when a session spans a prior workday. Those behaviours
are applied in the auth service; the tables just hold the state.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BrandScopedMixin, TimestampMixin, UUIDPkMixin
from app.db.types import brand_enum, device_type_enum
from app.models.enums import Brand, DeviceType


class Device(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    """A physical device, typed ONCE at setup. `brand` (from mixin) locks it."""
    __tablename__ = "device"

    type: Mapped[DeviceType] = mapped_column(device_type_enum, nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)


class Session(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "auth_session"

    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("device.id", ondelete="SET NULL"), nullable=True
    )
    # The brand context in effect. For the owner (brand switch) this is the
    # currently-selected brand; for locked crew it mirrors employee.brand.
    active_brand: Mapped[Brand | None] = mapped_column(brand_enum, nullable=True)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
