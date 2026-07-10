"""job

Revision ID: 7a252e66d735
Revises: 17f73ab4d872
Create Date: 2026-07-09 07:54:06.642418
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7a252e66d735'
down_revision: Union[str, None] = '17f73ab4d872'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# `brand` already exists -> reference (create_type=False). The 5 job enums are new.
brand = postgresql.ENUM('victoria', 'nanaimo', name='brand', create_type=False)
booking_lane = postgresql.ENUM('collect', 'invoiced', 'bins', 'pm', 'contracts', 'custom', 'pallet', name='booking_lane', create_type=False)
account_type = postgresql.ENUM('residential', 'commercial', 'property_mgmt', 'residential_bin', name='account_type', create_type=False)
job_status = postgresql.ENUM('unassigned', 'booked', 'done', 'awaiting_payment', 'unpaid', 'invoiced', name='job_status', create_type=False)
bin_action = postgresql.ENUM('drop', 'pickup', 'swap', name='bin_action', create_type=False)
customer_kind = postgresql.ENUM('residential', 'company', 'pm', 'contract', 'adhoc', name='customer_kind', create_type=False)

_NEW_ENUMS = (booking_lane, account_type, job_status, bin_action, customer_kind)


def upgrade() -> None:
    bind = op.get_bind()
    for e in _NEW_ENUMS:
        e.create(bind, checkfirst=True)

    op.create_table(
        'job',
        sa.Column('gcal_event_id', sa.String(length=256), nullable=True),
        sa.Column('booking_lane', booking_lane, nullable=False),
        sa.Column('account_type', account_type, nullable=True),
        sa.Column('status', job_status, nullable=False),
        sa.Column('assigned_truck_id', sa.UUID(), nullable=True),
        sa.Column('headline', sa.String(length=300), nullable=True),
        sa.Column('time_start', sa.Time(), nullable=True),
        sa.Column('time_end', sa.Time(), nullable=True),
        sa.Column('stack_order', sa.Integer(), nullable=True),
        sa.Column('customer_kind', customer_kind, nullable=True),
        sa.Column('residential_customer_id', sa.UUID(), nullable=True),
        sa.Column('company_customer_id', sa.UUID(), nullable=True),
        sa.Column('pm_building_id', sa.UUID(), nullable=True),
        sa.Column('contract_key', sa.String(length=80), nullable=True),
        sa.Column('customer_name', sa.String(length=180), nullable=True),
        sa.Column('customer_phone', sa.String(length=40), nullable=True),
        sa.Column('customer_email', sa.String(length=180), nullable=True),
        sa.Column('address', sa.String(length=255), nullable=True),
        sa.Column('town', sa.String(length=120), nullable=True),
        sa.Column('geo_lat', sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column('geo_lng', sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column('scope', sa.Text(), nullable=True),
        sa.Column('est_price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('quoted_price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('crew', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('equipment_needed', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('photos', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('bin_action', bin_action, nullable=True),
        sa.Column('bin_type', sa.String(length=40), nullable=True),
        sa.Column('bin_size', sa.String(length=20), nullable=True),
        sa.Column('bin_out_code', sa.String(length=20), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('brand', brand, nullable=False),
        sa.ForeignKeyConstraint(['assigned_truck_id'], ['truck.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['company_customer_id'], ['company_customer.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['pm_building_id'], ['pm_building.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['residential_customer_id'], ['residential_customer.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_job_brand'), 'job', ['brand'], unique=False)
    op.create_index(op.f('ix_job_gcal_event_id'), 'job', ['gcal_event_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_job_gcal_event_id'), table_name='job')
    op.drop_index(op.f('ix_job_brand'), table_name='job')
    op.drop_table('job')
    bind = op.get_bind()
    for e in _NEW_ENUMS:
        e.drop(bind, checkfirst=True)
