"""Bin-tracker driver-tool persistence — the field-captured state that the
driver's tool (`island-junk-bin-tracker`) produced only in-memory before now.

Three shapes, each faithful to its prototype localStorage key:

- **BinDriverDay** (`ij_binday_v1`) — the whole driver-day object (sign-in, walk-around,
  gear, odometer, clock in/out, EOD checklist), one row per (brand, driver, work_date),
  stored verbatim as JSONB. Write-only (office visibility + permanent tracking); the
  device's own localStorage restores same-device, and injecting a shared tablet's *other*
  driver's day would mix work (login-sessions spec), so it is deliberately not echoed back.
- **BinWeigh** (`ij_tares_v1` + `ij_weighins_v1`) — the current field weight per bin, one row
  per (brand, kind, k). These localStorage keys are *shared* stores written by several tools
  with slightly divergent record shapes, so the record is kept verbatim as JSONB and upserted
  per key (never a whole-blob clobber). Echoed back so the yard sees field weights.
- **ToolDailyLog** (`ij_tooldaily_v1`) — the morning onboard-gear check, one row per
  (brand, truck, log_date). Write-only compliance log.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BrandScopedMixin, TimestampMixin, UUIDPkMixin


class BinDriverDay(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    """`ij_binday_v1` — one driver's day (verbatim BD object). Unique per
    (brand, driver, work_date) so a re-sync upserts the same day."""
    __tablename__ = "bin_driver_day"
    __table_args__ = (UniqueConstraint("brand", "driver", "work_date", name="uq_binday_brand_driver_date"),)

    driver: Mapped[str] = mapped_column(String(120), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    truck: Mapped[str | None] = mapped_column(String(60), nullable=True)
    doc: Mapped[dict] = mapped_column(JSONB, nullable=False)   # the whole BD object


class BinWeigh(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    """`ij_tares_v1` / `ij_weighins_v1` — current field weight per bin. `kind` is
    'tare' or 'weighin'; `k` is the source dict key ('truck|code' for a tare, 'code'
    for a weigh-in). The record is stored verbatim (the writers disagree on fields)."""
    __tablename__ = "bin_weigh"
    __table_args__ = (UniqueConstraint("brand", "kind", "k", name="uq_binweigh_brand_kind_k"),)

    kind: Mapped[str] = mapped_column(String(12), nullable=False)   # tare | weighin
    k: Mapped[str] = mapped_column(String(60), nullable=False)      # dict key
    rec: Mapped[dict] = mapped_column(JSONB, nullable=False)        # verbatim record


class ToolDailyLog(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    """`ij_tooldaily_v1` — the morning onboard-gear check, one row per (brand, truck,
    log_date). Replaced wholesale for a truck+day (the prototype filters then pushes)."""
    __tablename__ = "tool_daily_log"
    __table_args__ = (UniqueConstraint("brand", "truck", "log_date", name="uq_tooldaily_brand_truck_date"),)

    truck: Mapped[str] = mapped_column(String(60), nullable=False)
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    who: Mapped[str | None] = mapped_column(String(120), nullable=True)
    logged_when: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "7:42am"
    tools: Mapped[dict] = mapped_column(JSONB, nullable=False)      # {name: on|miss}
