"""Job — the calendar-mirrored core record.

The booking screen is the ONLY calendar writer; after that the app reads/overlays
(colour = truck, vertical stack = route order, time = headline). Truck + status are
stored as SEPARATE fields; the Google colour is COMPUTED from them (never stored as
the source of truth). `assigned_truck_id` is set by reading the calendar colour
through `colour_map`.

Optional booking sub-objects (recurring, demolition, out_of_zone_travel,
old_materials_gate, po, paired_stops) live in the `details` JSONB bag — faithful to
the prototype's object storage and still fluid; promote to columns if they need indexing.
"""
from __future__ import annotations

import uuid
from datetime import time
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text, Time
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BrandScopedMixin, TimestampMixin, UUIDPkMixin
from app.db.types import (
    account_type_enum, bin_action_enum, booking_lane_enum, customer_kind_enum, job_status_enum,
)
from app.models.enums import AccountType, BinAction, BookingLane, CustomerKind, JobStatus


class Job(Base, UUIDPkMixin, TimestampMixin, BrandScopedMixin):
    __tablename__ = "job"

    # Calendar link — app writes at booking, mirrors thereafter.
    gcal_event_id: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)

    booking_lane: Mapped[BookingLane] = mapped_column(booking_lane_enum, nullable=False)
    account_type: Mapped[AccountType | None] = mapped_column(account_type_enum, nullable=True)
    status: Mapped[JobStatus] = mapped_column(job_status_enum, nullable=False, default=JobStatus.unassigned)

    # Dispatch (read from calendar colour + stack order). Colour computed from truck+status.
    assigned_truck_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("truck.id", ondelete="SET NULL"), nullable=True
    )
    headline: Mapped[str | None] = mapped_column(String(300), nullable=True)  # carries the real time
    time_start: Mapped[time | None] = mapped_column(Time, nullable=True)      # parsed from headline; never required
    time_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    stack_order: Mapped[int | None] = mapped_column(Integer, nullable=True)   # vertical position = route order

    # Customer — one of the FKs (or adhoc snapshot). customer_kind says which.
    customer_kind: Mapped[CustomerKind | None] = mapped_column(customer_kind_enum, nullable=True)
    residential_customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("residential_customer.id", ondelete="SET NULL"), nullable=True
    )
    company_customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company_customer.id", ondelete="SET NULL"), nullable=True
    )
    pm_building_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pm_building.id", ondelete="SET NULL"), nullable=True
    )
    contract_key: Mapped[str | None] = mapped_column(String(80), nullable=True)  # soft ref until contracts table exists
    customer_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(180), nullable=True)

    # Location (prototype matches on town; production geocodes the street address).
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    town: Mapped[str | None] = mapped_column(String(120), nullable=True)
    geo_lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    geo_lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)

    # Scope / pricing.
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    est_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    quoted_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)  # hard quote overrides est
    # Crew is MANDATORY on completed job data (guardrail §5) — enforced in app logic at
    # the work-save/completion step; nullable here because a freshly-booked job may not
    # have crew until the truck/colour is assigned.
    crew: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    equipment_needed: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    photos: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Bin-job specifics (booking_lane = bins).
    bin_action: Mapped[BinAction | None] = mapped_column(bin_action_enum, nullable=True)
    bin_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    bin_size: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bin_out_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Optional booking sub-objects (see module docstring).
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
