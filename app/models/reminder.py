"""Reminders (`ij_reminders_v1`) — the in-app reminder list, plus the §9/§11
48-hour residential-bin CC-charge reminder (auto-created; owner checks it off; the
charge itself stays manual, guardrail §2). Brand-scoped.
"""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BrandScopedMixin, TimestampMixin, UUIDPkMixin
from app.db.types import reminder_kind_enum
from app.models.enums import ReminderKind


class Reminder(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    __tablename__ = "reminder"
    __table_args__ = (UniqueConstraint("brand", "source_id", name="uq_reminder_brand_source"),)

    source_id: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    kind: Mapped[ReminderKind] = mapped_column(reminder_kind_enum, nullable=False, default=ReminderKind.general)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)    # prototype Date.now() ms epoch
    due: Mapped[date | None] = mapped_column(Date, nullable=True)
    done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    booking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    addr: Mapped[str | None] = mapped_column(String(255), nullable=True)
    draft: Mapped[dict | None] = mapped_column(JSONB, nullable=True)     # booking-draft payload (Resume booking)
    # cc_charge only: the off-board reminder calendar it belongs on + the source job.
    calendar: Mapped[str | None] = mapped_column(String(120), nullable=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job.id", ondelete="SET NULL"), nullable=True, index=True
    )
