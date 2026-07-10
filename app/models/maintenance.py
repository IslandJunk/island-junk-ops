"""Maintenance domain — the maintenance hub's asset ledger and the crew's
walk-around defect flags. Brand-scoped.

The maintenance hub (`ij_maint_v2`) is a rich, versioned, nested document
(`{order, m:{key: asset}, _v}`) with client-side migrations; faithfully preserving
it (and not fighting those migrations) means storing the whole thing as one JSONB
document per brand — the same JSONB-for-nested approach used elsewhere. Defect flags
(`ij_fixes_v1`) are a flat cross-screen list (truck-hub reports, yard/maintenance
closes), so they get a real table.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BrandScopedMixin, TimestampMixin, UUIDPkMixin


class MaintenanceDoc(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    """One row per brand: the whole `ij_maint_v2` document (`{order, m, _v}`)."""
    __tablename__ = "maintenance_doc"
    __table_args__ = (UniqueConstraint("brand", name="uq_maintenance_doc_brand"),)

    doc: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class DefectFlag(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    """`ij_fixes_v1` — a crew walk-around issue. truck-hub writes it open; the
    maintenance/yard hub closes it (`ij_fixes_resolved_v1`)."""
    __tablename__ = "defect_flag"
    __table_args__ = (UniqueConstraint("brand", "source_id", name="uq_defect_flag_brand_source"),)

    source_id: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    truck: Mapped[str | None] = mapped_column(String(60), nullable=True)
    item: Mapped[str | None] = mapped_column(String(180), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    who: Mapped[str | None] = mapped_column(String(120), nullable=True)
    flag_date: Mapped[str | None] = mapped_column(String(20), nullable=True)   # prototype `date` (iso string)
    source: Mapped[str | None] = mapped_column(String(40), nullable=True)      # e.g. 'walk-around'
    is_open: Mapped[bool] = mapped_column("open", Boolean, nullable=False, default=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
