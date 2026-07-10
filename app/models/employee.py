"""Employee = login + access source of truth (`ij_employees_v1`).

Brand handling is the one exception to BrandScopedMixin: the **owner** row is
shared across both brands (brand = NULL); every other employee is locked to one
brand. So this model declares `brand` nullable directly instead of using the
NOT-NULL mixin.
"""
from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin
from app.db.types import brand_enum, pay_type_enum
from app.models.enums import Brand, PayType


class Employee(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "employee"

    # NULL = owner (all brands). Non-owner rows must carry a brand (enforced in app logic).
    brand: Mapped[Brand | None] = mapped_column(brand_enum, nullable=True, index=True)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Free-text, pattern-matched (/owner/i, /manager/i, /yard/, /bin/) — keep substrings meaningful.
    role: Mapped[str] = mapped_column(String(60), nullable=False, default="Crew")

    # 4-digit PIN, stored hashed (pbkdf2). Server-side rate-limit/lockout does the real work.
    pin_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Feature flags (see ACCESS_FLAGS). Postgres text[].
    access: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # false for Owner + Main manager -> excluded from punch clock / payroll.
    time_tracked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    pay_type: Mapped[PayType] = mapped_column(pay_type_enum, nullable=False, default=PayType.hourly)

    can_clock_others: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    see_all_trucks: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    edit_all_trucks: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Employee {self.name!r} role={self.role!r} brand={self.brand}>"
