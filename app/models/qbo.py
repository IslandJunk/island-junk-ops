"""QuickBooks Online connection (WS4) — the stored OAuth link for a brand's QB company.

READ-ONLY sync: the app reads QBO to detect invoice-sent + paid; it NEVER writes to QBO. This
table holds the OAuth tokens (per brand) + the auto-sync toggle. One logical connection per brand
(the latest active row, updated in place on reconnect). Access/refresh tokens are SECRETS — they
let the background sync refresh without the owner re-consenting; encryption-at-rest is a
security-review item before production (task 7).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BrandScopedMixin, TimestampMixin, UUIDPkMixin
from app.db.crypto import EncryptedText


class QboConnection(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    """A brand's QuickBooks Online OAuth connection (read-only). Updated in place on reconnect."""
    __tablename__ = "qbo_connection"

    realm_id: Mapped[str] = mapped_column(String(32), nullable=False)          # QBO company id
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # OAuth tokens (SECRETS). Access ~1h; refresh ~100 days and ROTATES on each refresh
    # (always persist the newly-returned refresh token).
    access_token: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    access_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    refresh_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Owner-Hub on/off switch. Default OFF — manual-first; the owner enables auto-sync when ready.
    auto_sync_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Polling cursor for the read-only sync (timestamp of the last successful QBO read).
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    connected_by: Mapped[str | None] = mapped_column(String(120), nullable=True)   # the owner
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
