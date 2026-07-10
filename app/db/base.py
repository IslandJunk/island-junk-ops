"""Declarative base + mixins shared by every model.

Brand-scoping is the core architectural rule (CLAUDE.md §3): every operational
row carries a `brand`. The owner account and owner-security are the only shared
rows and deliberately do NOT use BrandScopedMixin.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db.types import brand_enum
from app.models.enums import Brand


class Base(DeclarativeBase):
    pass


class UUIDPkMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class BrandScopedMixin:
    """Every operational table mixes this in. Owner-level rows do not."""
    brand: Mapped[Brand] = mapped_column(brand_enum, nullable=False, index=True)
