"""trucks and customers

Revision ID: 17f73ab4d872
Revises: 980268b91d57
Create Date: 2026-07-09 07:50:09.688796
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '17f73ab4d872'
down_revision: Union[str, None] = '980268b91d57'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# `brand` already exists -> reference it (create_type=False, don't re-create).
brand = postgresql.ENUM('victoria', 'nanaimo', name='brand', create_type=False)
# New enums -> create once (checkfirst) in upgrade(); columns reference create_type=False.
customer_source = postgresql.ENUM('seed', 'app', 'qb', name='customer_source', create_type=False)
truck_kind = postgresql.ENUM('hands_on', 'bin', name='truck_kind', create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    customer_source.create(bind, checkfirst=True)
    truck_kind.create(bind, checkfirst=True)

    op.create_table(
        'company_customer',
        sa.Column('co', sa.String(length=180), nullable=False),
        sa.Column('name', sa.String(length=180), nullable=True),
        sa.Column('addr', sa.String(length=255), nullable=True),
        sa.Column('contact', sa.String(length=120), nullable=True),
        sa.Column('phone', sa.String(length=40), nullable=True),
        sa.Column('email', sa.String(length=180), nullable=True),
        sa.Column('accounts', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('src', customer_source, nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('brand', brand, nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_company_customer_brand'), 'company_customer', ['brand'], unique=False)

    op.create_table(
        'pm_company',
        sa.Column('nm', sa.String(length=180), nullable=False),
        sa.Column('addr', sa.String(length=255), nullable=True),
        sa.Column('email', sa.String(length=180), nullable=True),
        sa.Column('contact', sa.String(length=120), nullable=True),
        sa.Column('phone', sa.String(length=40), nullable=True),
        sa.Column('src', customer_source, nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('brand', brand, nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_pm_company_brand'), 'pm_company', ['brand'], unique=False)

    op.create_table(
        'residential_customer',
        sa.Column('first', sa.String(length=120), nullable=True),
        sa.Column('last', sa.String(length=120), nullable=True),
        sa.Column('phone', sa.String(length=40), nullable=True),
        sa.Column('email', sa.String(length=180), nullable=True),
        sa.Column('addr', sa.String(length=255), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('brand', brand, nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_residential_customer_brand'), 'residential_customer', ['brand'], unique=False)

    op.create_table(
        'truck',
        sa.Column('num', sa.String(length=20), nullable=False),
        sa.Column('lead', sa.String(length=120), nullable=True),
        sa.Column('kind', truck_kind, nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('brand', brand, nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('brand', 'num', name='uq_truck_brand_num'),
    )
    op.create_index(op.f('ix_truck_brand'), 'truck', ['brand'], unique=False)

    op.create_table(
        'pm_group',
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('nm', sa.String(length=180), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('brand', brand, nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['pm_company.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_pm_group_brand'), 'pm_group', ['brand'], unique=False)
    op.create_index(op.f('ix_pm_group_company_id'), 'pm_group', ['company_id'], unique=False)

    op.create_table(
        'truck_alert_pref',
        sa.Column('truck_id', sa.UUID(), nullable=False),
        sa.Column('reassign', sa.Boolean(), nullable=False),
        sa.Column('swap', sa.Boolean(), nullable=False),
        sa.Column('metal', sa.Boolean(), nullable=False),
        sa.Column('weigh', sa.Boolean(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['truck_id'], ['truck.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('truck_id'),
    )

    op.create_table(
        'pm_building',
        sa.Column('group_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=180), nullable=True),
        sa.Column('address', sa.String(length=255), nullable=True),
        sa.Column('email', sa.String(length=180), nullable=True),
        sa.Column('contact', sa.String(length=120), nullable=True),
        sa.Column('phone', sa.String(length=40), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('brand', brand, nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['pm_group.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_pm_building_brand'), 'pm_building', ['brand'], unique=False)
    op.create_index(op.f('ix_pm_building_group_id'), 'pm_building', ['group_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_pm_building_group_id'), table_name='pm_building')
    op.drop_index(op.f('ix_pm_building_brand'), table_name='pm_building')
    op.drop_table('pm_building')
    op.drop_table('truck_alert_pref')
    op.drop_index(op.f('ix_pm_group_company_id'), table_name='pm_group')
    op.drop_index(op.f('ix_pm_group_brand'), table_name='pm_group')
    op.drop_table('pm_group')
    op.drop_index(op.f('ix_truck_brand'), table_name='truck')
    op.drop_table('truck')
    op.drop_index(op.f('ix_residential_customer_brand'), table_name='residential_customer')
    op.drop_table('residential_customer')
    op.drop_index(op.f('ix_pm_company_brand'), table_name='pm_company')
    op.drop_table('pm_company')
    op.drop_index(op.f('ix_company_customer_brand'), table_name='company_customer')
    op.drop_table('company_customer')
    bind = op.get_bind()
    truck_kind.drop(bind, checkfirst=True)
    customer_source.drop(bind, checkfirst=True)
