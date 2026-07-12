"""Card-on-file (WS3) — residential-bin card charging (Wes's sanctioned guardrail change;
docs/bin-payments-and-calendar-plan.md).

We store ONLY Square TOKENS — never the card number or CVV. A `StoredCard` is a customer's
card saved *in Square* (we keep the Square customer + card ids + brand/last4 for display + the
authorization). A `CardCharge` is the append-only audit of one owner-pressed charge. Brand-scoped.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BrandScopedMixin, TimestampMixin, UUIDPkMixin


class StoredCard(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    """A customer's card saved on file IN SQUARE. We hold only the Square customer + card tokens
    plus brand/last4 (for display) and the card-on-file authorization. NEVER the PAN or CVV.
    Customer-level (reusable across that customer's future bins). `created_at` = authorized-at."""
    __tablename__ = "stored_card"

    residential_customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("residential_customer.id", ondelete="SET NULL"),
        nullable=True, index=True)
    customer_name: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)

    square_customer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    square_card_id: Mapped[str] = mapped_column(String(80), nullable=False)   # the ccof: token
    card_brand: Mapped[str | None] = mapped_column(String(24), nullable=True)  # VISA, MASTERCARD…
    card_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    exp_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exp_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Card-on-file authorization — what stands behind a disputed charge.
    authorized_by: Mapped[str | None] = mapped_column(String(120), nullable=True)   # the manager
    auth_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CardCharge(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    """Append-only audit of ONE owner-pressed charge of a StoredCard (guardrail: owner-only,
    never automatic). `created_at` = when it was charged; `created_by` = the owner."""
    __tablename__ = "card_charge"

    stored_card_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stored_card.id", ondelete="SET NULL"), nullable=True, index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job.id", ondelete="SET NULL"), nullable=True, index=True)
    amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    square_payment_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str | None] = mapped_column(String(24), nullable=True)   # COMPLETED / DECLINED / ERROR
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)   # the owner
