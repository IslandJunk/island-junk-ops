"""Customer references — residential, commercial company, and the 3-level
property-management tree. Brand-scoped. Dedupe (digits-only phone for residential,
lowercased company name for commercial) is handled in app logic on import, so no
hard DB uniqueness here yet (QuickBooks imports may need interactive de-duping).
"""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, text as sa_text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BrandScopedMixin, TimestampMixin, UUIDPkMixin
from app.db.types import customer_source_enum
from app.models.enums import CustomerSource


class ResidentialCustomer(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    """`ij_customers_v1` — return-customer autofill (prod source: QuickBooks import)."""
    __tablename__ = "residential_customer"

    first: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    addr: Mapped[str | None] = mapped_column(String(255), nullable=True)


class CompanyCustomer(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    """`ij_company_customers_v1` — commercial accounts."""
    __tablename__ = "company_customer"

    co: Mapped[str] = mapped_column(String(180), nullable=False)          # company name
    name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    addr: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    accounts: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)  # departments/locations
    # {location name -> that site's JOB address}. Purely ADDITIVE to `accounts` (which stays the plain
    # name list every other reader uses), so picking a saved location can auto-fill the address the
    # crew drive to — instead of the manager retyping it on every booking.
    account_addrs: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=sa_text("'{}'::jsonb")
    )
    src: Mapped[CustomerSource] = mapped_column(customer_source_enum, nullable=False, default=CustomerSource.app)


class PmCompany(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    """`ij_pm_db_v2` top level — a property-management firm."""
    __tablename__ = "pm_company"

    nm: Mapped[str] = mapped_column(String(180), nullable=False)
    addr: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    contact: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    src: Mapped[CustomerSource] = mapped_column(customer_source_enum, nullable=False, default=CustomerSource.app)


class PmGroup(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    """Middle level — a grouping under a PM firm ('' = unfiled)."""
    __tablename__ = "pm_group"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pm_company.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nm: Mapped[str] = mapped_column(String(180), nullable=False, default="")


class PmBuilding(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    """Leaf — a managed building/address under a group."""
    __tablename__ = "pm_building"

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pm_group.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    contact: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
