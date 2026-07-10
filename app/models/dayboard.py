"""Day-board crew overlays — the manager/crew's live annotations laid over the
calendar-authoritative dispatch board (day-board prototype), keyed by the Google
Calendar **event id** (the board's stop id). Three localStorage keys collapse into
one row per (brand, event_id):

- `ij_dayboard_status_v1` -> `status` (a crew status override for that stop)
- `ij_dayboard_notes_v1`  -> `note`   (a free-text crew note)
- `ij_dayboard_sitelog_v1`-> `sitelog` (`{start, finish, loc}` on-site log)

Decoupled from `job` on purpose: a board stop is a calendar event that may or may
not have an app-booked Job behind it (the manager also creates events directly).
"""
from __future__ import annotations

from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BrandScopedMixin, TimestampMixin, UUIDPkMixin


class DayboardOverlay(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    __tablename__ = "dayboard_overlay"
    __table_args__ = (UniqueConstraint("brand", "event_id", name="uq_dayboard_brand_event"),)

    event_id: Mapped[str] = mapped_column(String(1024), nullable=False)   # Google Calendar event id
    status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    sitelog: Mapped[dict | None] = mapped_column(JSONB, nullable=True)     # {start, finish, loc}
