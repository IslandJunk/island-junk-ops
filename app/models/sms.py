"""SMS persistence (island-junk-SPEC-sms-and-texting.md).

- **SmsOptOut** — numbers that texted STOP. The updates line is ONE shared number, so an
  opt-out is global per number (blocks sends for both brands). No brand scope on purpose.
- **SmsMessage** — a log of every message in/out (spec §3.3 "record the inbound message";
  also an outbound audit). `brand` is nullable — an inbound from an unrecognised sender has
  no brand until matched — so this does NOT use BrandScopedMixin.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin
from app.db.types import brand_enum
from app.models.enums import Brand


class SmsOptOut(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "sms_opt_out"

    number: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)  # E.164
    opted_out_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)


class SmsMessage(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "sms_message"

    direction: Mapped[str] = mapped_column(String(3), nullable=False)   # in | out
    number: Mapped[str] = mapped_column(String(20), nullable=False)     # the customer's number (E.164)
    brand: Mapped[Brand | None] = mapped_column(brand_enum, nullable=True, index=True)
    kind: Mapped[str | None] = mapped_column(String(30), nullable=True)  # booking_confirm|on_our_way|eta|reminder|completion|auto_reply|stop|help|inbound
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    twilio_sid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sent: Mapped[bool] = mapped_column(nullable=False, default=False)   # False in dry-run (composed, not sent)
