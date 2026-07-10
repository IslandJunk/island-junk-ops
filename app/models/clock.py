"""Clock punches (`ij_clock_log`) — one row per (employee, work day). Clock strings
are kept verbatim ("7:30am") as the prototype records them; the owner computes hours.
Unique per (brand, name, date) so re-syncs upsert the same day's punch.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BrandScopedMixin, TimestampMixin, UUIDPkMixin


class ClockPunch(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    __tablename__ = "clock_punch"
    __table_args__ = (UniqueConstraint("brand", "employee_name", "work_date", name="uq_clock_brand_name_date"),)

    employee_name: Mapped[str] = mapped_column(String(120), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    in_time: Mapped[str | None] = mapped_column(String(20), nullable=True)    # "7:30am"
    out_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    done_time: Mapped[str | None] = mapped_column(String(20), nullable=True)  # end-of-day checklist done
    truck: Mapped[str | None] = mapped_column(String(60), nullable=True)
