"""Job photo — a reference photo attached to a Job so the crew see it on the Day Board
stop detail (§8: bring the customer's photos into the job instead of a separate group).

Stored in-app as compressed image bytes; the client downscales/compresses before upload,
so rows stay small. Low volume by design (manager-attached reference shots, not the crew's
before/after stream — those stay in Messenger). Move to object storage if it ever grows.
"""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class JobPhoto(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "job_photo"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False, default="image/jpeg")
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    uploaded_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
