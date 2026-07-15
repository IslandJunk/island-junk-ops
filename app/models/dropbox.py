"""Dropbox connection — the stored OAuth link to Wes's Dropbox account (§4/§10).

Unlike QuickBooks (a separate company per brand), Dropbox is ONE account; the brand is expressed
by the folder path (dropbox_root + brand), so this is a single shared connection row (like
owner_security), not brand-scoped. Access/refresh tokens are SECRETS — encrypted at rest with the
same Fernet key as QBO. Dropbox refresh tokens do NOT expire or rotate; the short-lived access
token (~4h) is refreshed on demand.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin
from app.db.crypto import EncryptedText


class DropboxConnection(Base, UUIDPkMixin, TimestampMixin):
    """The single Dropbox OAuth connection (Wes's account). Updated in place on reconnect."""
    __tablename__ = "dropbox_connection"

    account_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    account_email: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # OAuth tokens (SECRETS). Access ~4h; refresh is long-lived and does NOT rotate.
    access_token: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    access_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)

    connected_by: Mapped[str | None] = mapped_column(String(120), nullable=True)   # the owner
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
