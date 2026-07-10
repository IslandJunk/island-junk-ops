"""Incident reports (`ij_incidents_v1`). Fields kept as strings (not enums) to match
the prototype's free-ish sets without an enum migration. `source_id` is the
prototype's `inc...` id, unique per brand so re-syncs don't duplicate.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BrandScopedMixin, TimestampMixin, UUIDPkMixin


class Incident(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    __tablename__ = "incident"
    __table_args__ = (UniqueConstraint("brand", "source_id", name="uq_incident_brand_source"),)

    source_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    sev: Mapped[str | None] = mapped_column(String(40), nullable=True)
    told: Mapped[str | None] = mapped_column(String(60), nullable=True)
    reported_by: Mapped[str | None] = mapped_column(String(120), nullable=True)   # prototype `by`
    who: Mapped[str | None] = mapped_column(String(255), nullable=True)
    incident_date: Mapped[date | None] = mapped_column(Date, nullable=True)       # prototype `date`
    incident_time: Mapped[str | None] = mapped_column(String(20), nullable=True)  # prototype `time`
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)      # prototype `where`
    truck: Mapped[str | None] = mapped_column(String(60), nullable=True)
    what: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str | None] = mapped_column(Text, nullable=True)
    photos: Mapped[list | None] = mapped_column(JSONB, nullable=True)
