"""Office day-notes + a small brand-settings KV.

- **DayNote** (`ij_daynotes_v1` = `{date: {bin, yard, handson}}`) — the office's morning
  note per shift, one row per (brand, note_date); the crew tools read the shift they care
  about (the bin-tracker reads `bin`, etc.). Per-shift present-key upsert (a writer that
  only sets one shift never blanks the others).
- **BrandSetting** (`ij_binsout_cfg_v1` and future 1-off settings) — a generic
  (brand, key) -> JSONB value, so small owner/manager settings get a home without a
  bespoke table each.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BrandScopedMixin, TimestampMixin, UUIDPkMixin


class DayNote(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    __tablename__ = "day_note"
    __table_args__ = (UniqueConstraint("brand", "note_date", name="uq_daynote_brand_date"),)

    note_date: Mapped[date] = mapped_column(Date, nullable=False)
    bin: Mapped[str | None] = mapped_column(Text, nullable=True)
    yard: Mapped[str | None] = mapped_column(Text, nullable=True)
    handson: Mapped[str | None] = mapped_column(Text, nullable=True)


class BrandSetting(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    __tablename__ = "brand_setting"
    __table_args__ = (UniqueConstraint("brand", "key", name="uq_setting_brand_key"),)

    key: Mapped[str] = mapped_column(String(80), nullable=False)   # e.g. "ij_binsout_cfg_v1"
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)     # verbatim value object
