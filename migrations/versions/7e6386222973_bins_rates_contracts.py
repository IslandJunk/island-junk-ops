"""bins rates contracts

Revision ID: 7e6386222973
Revises: 7a252e66d735
Create Date: 2026-07-09 08:01:09.681025
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7e6386222973'
down_revision: Union[str, None] = '7a252e66d735'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# `brand` already exists -> reference (create_type=False). Three new enums.
brand = postgresql.ENUM('victoria', 'nanaimo', name='brand', create_type=False)
bin_status = postgresql.ENUM('idle', 'reserved', 'dropped', 'returning', 'returned', 'to_sort', 'clearing', 'ready_dump', 'weighing', 'full', 'maintenance', 'retired', name='bin_status', create_type=False)
contract_pricing = postgresql.ENUM('commercial', 'hourly', 'flatmonthly', 'flatjob', name='contract_pricing', create_type=False)
disposal_role = postgresql.ENUM('cost', 'income', 'free', 'sort', name='disposal_role', create_type=False)
_NEW_ENUMS = (bin_status, contract_pricing, disposal_role)


def upgrade() -> None:
    bind = op.get_bind()
    for e in _NEW_ENUMS:
        e.create(bind, checkfirst=True)
    op.create_table('area_surcharge',
    sa.Column('area_name', sa.String(length=120), nullable=False),
    sa.Column('aliases', postgresql.ARRAY(sa.String()), nullable=False),
    sa.Column('hand_amount', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('bin_amount', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('is_base', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('brand', brand, nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_area_surcharge_brand'), 'area_surcharge', ['brand'], unique=False)
    op.create_table('contract',
    sa.Column('key', sa.String(length=80), nullable=False),
    sa.Column('name', sa.String(length=180), nullable=False),
    sa.Column('short', sa.String(length=120), nullable=True),
    sa.Column('pricing', contract_pricing, nullable=False),
    sa.Column('rate_key', sa.String(length=80), nullable=True),
    sa.Column('divisions', postgresql.ARRAY(sa.String()), nullable=False),
    sa.Column('route_divs', postgresql.ARRAY(sa.String()), nullable=False),
    sa.Column('div_addable', sa.Boolean(), nullable=False),
    sa.Column('extra', sa.String(length=20), nullable=True),
    sa.Column('bin', sa.Boolean(), nullable=False),
    sa.Column('po_req', sa.Boolean(), nullable=False),
    sa.Column('site_log', sa.Boolean(), nullable=False),
    sa.Column('shots', postgresql.ARRAY(sa.String()), nullable=False),
    sa.Column('terms', sa.Text(), nullable=True),
    sa.Column('rates', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('flat', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('flat_unit', sa.String(length=40), nullable=True),
    sa.Column('properties', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('brand', brand, nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('brand', 'key', name='uq_contract_brand_key')
    )
    op.create_index(op.f('ix_contract_brand'), 'contract', ['brand'], unique=False)
    op.create_table('disposal_facility',
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('role', disposal_role, nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('brand', brand, nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_disposal_facility_brand'), 'disposal_facility', ['brand'], unique=False)
    op.create_table('rate_card',
    sa.Column('labour_rate', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('demo_rate', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('crew_extra_rate', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('recycle_charge', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('diversion_surcharge', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('diversion_report', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('gst_pct', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('card_fee_pct', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('parking', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('travel', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('residential_loads', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('commercial_loads', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('residential_min', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('commercial_included_min', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('specials', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('ppe', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('bin_rates', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('yard_waste', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('brand', brand, nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('brand', name='uq_rate_card_brand')
    )
    op.create_index(op.f('ix_rate_card_brand'), 'rate_card', ['brand'], unique=False)
    op.create_table('disposal_material',
    sa.Column('m', sa.String(length=120), nullable=False),
    sa.Column('facility_id', sa.UUID(), nullable=True),
    sa.Column('cost', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('unit', sa.String(length=20), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('brand', brand, nullable=False),
    sa.ForeignKeyConstraint(['facility_id'], ['disposal_facility.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_disposal_material_brand'), 'disposal_material', ['brand'], unique=False)
    op.create_table('disposal_rate_history',
    sa.Column('material_id', sa.UUID(), nullable=True),
    sa.Column('m', sa.String(length=120), nullable=True),
    sa.Column('cost', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('unit', sa.String(length=20), nullable=True),
    sa.Column('effective_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('changed_by', sa.String(length=120), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('brand', brand, nullable=False),
    sa.ForeignKeyConstraint(['material_id'], ['disposal_material.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_disposal_rate_history_brand'), 'disposal_rate_history', ['brand'], unique=False)
    op.create_index(op.f('ix_disposal_rate_history_material_id'), 'disposal_rate_history', ['material_id'], unique=False)
    op.create_table('bin',
    sa.Column('code', sa.String(length=12), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('lidded', sa.Boolean(), nullable=False),
    sa.Column('custom_lid', sa.Boolean(), nullable=False),
    sa.Column('leased', sa.Boolean(), nullable=False),
    sa.Column('stationed', sa.Boolean(), nullable=False),
    sa.Column('type', sa.String(length=60), nullable=True),
    sa.Column('roofing', sa.Boolean(), nullable=False),
    sa.Column('condition', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('status', bin_status, nullable=False),
    sa.Column('customer', sa.String(length=180), nullable=True),
    sa.Column('address', sa.String(length=255), nullable=True),
    sa.Column('town', sa.String(length=120), nullable=True),
    sa.Column('job_id', sa.UUID(), nullable=True),
    sa.Column('drop_date', sa.Date(), nullable=True),
    sa.Column('drop_time', sa.Time(), nullable=True),
    sa.Column('pick_date', sa.Date(), nullable=True),
    sa.Column('scheduled_pickup', sa.Date(), nullable=True),
    sa.Column('hq_time', sa.Time(), nullable=True),
    sa.Column('last_dumped', sa.Date(), nullable=True),
    sa.Column('yard_at', sa.Time(), nullable=True),
    sa.Column('base', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('surcharge', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('gross', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('tare', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('gross_f', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('gross_r', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('tare_f', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('tare_r', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('waste_class', sa.String(length=120), nullable=True),
    sa.Column('dump_fee', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('fee_split', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('extra_time', sa.String(length=120), nullable=True),
    sa.Column('pickup_by', sa.String(length=120), nullable=True),
    sa.Column('dump_by', sa.String(length=120), nullable=True),
    sa.Column('sort_junk', sa.String(length=120), nullable=True),
    sa.Column('sort_metal', sa.String(length=120), nullable=True),
    sa.Column('sort_minutes', sa.Integer(), nullable=True),
    sa.Column('no_sort', sa.Boolean(), nullable=False),
    sa.Column('cleared', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('photos', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('contact_log', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('repair_note', sa.String(length=255), nullable=True),
    sa.Column('repair_open', sa.Boolean(), nullable=False),
    sa.Column('repair_at', sa.Date(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('brand', brand, nullable=False),
    sa.ForeignKeyConstraint(['job_id'], ['job.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('brand', 'code', name='uq_bin_brand_code')
    )
    op.create_index(op.f('ix_bin_brand'), 'bin', ['brand'], unique=False)
    op.create_table('surcharge_waiver',
    sa.Column('job_id', sa.UUID(), nullable=True),
    sa.Column('area_id', sa.UUID(), nullable=True),
    sa.Column('kind', sa.String(length=20), nullable=True),
    sa.Column('waived_by', sa.String(length=120), nullable=True),
    sa.Column('at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('brand', brand, nullable=False),
    sa.ForeignKeyConstraint(['area_id'], ['area_surcharge.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['job_id'], ['job.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_surcharge_waiver_brand'), 'surcharge_waiver', ['brand'], unique=False)
    op.create_index(op.f('ix_surcharge_waiver_job_id'), 'surcharge_waiver', ['job_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_surcharge_waiver_job_id'), table_name='surcharge_waiver')
    op.drop_index(op.f('ix_surcharge_waiver_brand'), table_name='surcharge_waiver')
    op.drop_table('surcharge_waiver')
    op.drop_index(op.f('ix_bin_brand'), table_name='bin')
    op.drop_table('bin')
    op.drop_index(op.f('ix_disposal_rate_history_material_id'), table_name='disposal_rate_history')
    op.drop_index(op.f('ix_disposal_rate_history_brand'), table_name='disposal_rate_history')
    op.drop_table('disposal_rate_history')
    op.drop_index(op.f('ix_disposal_material_brand'), table_name='disposal_material')
    op.drop_table('disposal_material')
    op.drop_index(op.f('ix_rate_card_brand'), table_name='rate_card')
    op.drop_table('rate_card')
    op.drop_index(op.f('ix_disposal_facility_brand'), table_name='disposal_facility')
    op.drop_table('disposal_facility')
    op.drop_index(op.f('ix_contract_brand'), table_name='contract')
    op.drop_table('contract')
    op.drop_index(op.f('ix_area_surcharge_brand'), table_name='area_surcharge')
    op.drop_table('area_surcharge')
    bind = op.get_bind()
    for e in _NEW_ENUMS:
        e.drop(bind, checkfirst=True)
