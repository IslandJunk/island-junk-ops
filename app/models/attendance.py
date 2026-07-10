"""Attendance + break logs — the manager/owner HR overlays that were device-local.

- **Attendance** (`ij_attendance_v1` = `{date: {name: {status, note, lateTime}}}`) — one
  row per (brand, work_date, employee_name). Permanent HR record; upsert-only.
- **BreakLog** (`ij_breaks_v1` = `{name: {iso: {…, total}}}`) — one row per (brand,
  employee_name, work_date); the break record is kept verbatim as JSONB (its inner shape
  varies) with `total_minutes` lifted out for the owner's hours math.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BrandScopedMixin, TimestampMixin, UUIDPkMixin


class Attendance(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("brand", "work_date", "employee_name", name="uq_attendance_brand_date_name"),)

    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    employee_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)   # ""|yes|late|sick|off|other
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    late_time: Mapped[str | None] = mapped_column(String(20), nullable=True)


class BreakLog(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    __tablename__ = "break_log"
    __table_args__ = (UniqueConstraint("brand", "employee_name", "work_date", name="uq_break_brand_name_date"),)

    employee_name: Mapped[str] = mapped_column(String(120), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    doc: Mapped[dict] = mapped_column(JSONB, nullable=False)   # the verbatim break record
