"""Owner Hub gate + 2FA (`ij_owner_sec_v1`) — GLOBAL / shared, not per-brand.

The owner has TWO credentials: the 4-digit `pin` on their employee row (Main Hub
tile) and this password + 2FA (Owner Hub gate). This table is intentionally a
single shared row (no brand column) — the owner account spans both brands.
"""
from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class OwnerSecurity(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "owner_security"

    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # [{id, label, number}] — 2FA destinations
    phones: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    # [{code, used}] — one-time recovery codes
    backup_codes: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    # [{at, action, detail, brand}] — owner action audit, capped in app logic (~500)
    audit_log: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
