"""Shared SQLAlchemy enum type objects.

Reuse the SAME instance across every column so Postgres emits only one
CREATE TYPE per enum (avoids "type already exists" on migrate).
"""
from __future__ import annotations

from sqlalchemy import Enum as SAEnum

from app.models.enums import (
    AccountType, BinAction, BinStatus, BookingLane, Brand, ColourKind, ContractPricing,
    CustomerKind, CustomerSource, DeviceType, DisposalRole, JobStatus, PayType, TruckKind,
)

brand_enum = SAEnum(Brand, name="brand")
device_type_enum = SAEnum(DeviceType, name="device_type")
pay_type_enum = SAEnum(PayType, name="pay_type")
colour_kind_enum = SAEnum(ColourKind, name="colour_kind")
truck_kind_enum = SAEnum(TruckKind, name="truck_kind")
customer_source_enum = SAEnum(CustomerSource, name="customer_source")
booking_lane_enum = SAEnum(BookingLane, name="booking_lane")
account_type_enum = SAEnum(AccountType, name="account_type")
job_status_enum = SAEnum(JobStatus, name="job_status")
bin_action_enum = SAEnum(BinAction, name="bin_action")
customer_kind_enum = SAEnum(CustomerKind, name="customer_kind")
bin_status_enum = SAEnum(BinStatus, name="bin_status")
contract_pricing_enum = SAEnum(ContractPricing, name="contract_pricing")
disposal_role_enum = SAEnum(DisposalRole, name="disposal_role")
