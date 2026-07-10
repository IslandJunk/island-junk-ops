"""Field jobs (`ij_jobs_v1`) — the crew-side, multi-visit on-site record that rolls
up to one invoice (distinct from the calendar `job`). Visits are stored as JSONB
(faithful to the prototype's nested shape). Upserted by the prototype's `id`.
"""
from __future__ import annotations

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BrandScopedMixin, TimestampMixin, UUIDPkMixin


class FieldJob(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    __tablename__ = "field_job"
    __table_args__ = (UniqueConstraint("brand", "source_id", name="uq_field_job_brand_source"),)

    source_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    type: Mapped[str | None] = mapped_column(String(30), nullable=True)     # residential | commercial
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)   # open | done
    customer: Mapped[str | None] = mapped_column(String(180), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    visits: Mapped[list | None] = mapped_column(JSONB, nullable=True)        # [{date, crew, summary, totals}]
