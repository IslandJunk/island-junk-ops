"""initial auth and refs

Revision ID: 2263e99c12d8
Revises:
Create Date: 2026-07-09 07:28:08.377809
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2263e99c12d8'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Shared enum types. `brand` is used by three tables, so create each type ONCE
# (checkfirst=True) and reference it with create_type=False on the columns —
# otherwise the second CREATE TABLE re-issues CREATE TYPE and fails.
brand = postgresql.ENUM('victoria', 'nanaimo', name='brand', create_type=False)
device_type = postgresql.ENUM('shared_tablet', 'personal_phone', name='device_type', create_type=False)
pay_type = postgresql.ENUM('salaried', 'hourly', name='pay_type', create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    brand.create(bind, checkfirst=True)
    device_type.create(bind, checkfirst=True)
    pay_type.create(bind, checkfirst=True)

    op.create_table(
        'device',
        sa.Column('type', device_type, nullable=False),
        sa.Column('label', sa.String(length=120), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('brand', brand, nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_device_brand'), 'device', ['brand'], unique=False)

    op.create_table(
        'employee',
        sa.Column('brand', brand, nullable=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('role', sa.String(length=60), nullable=False),
        sa.Column('pin_hash', sa.String(length=255), nullable=False),
        sa.Column('access', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('time_tracked', sa.Boolean(), nullable=False),
        sa.Column('pay_type', pay_type, nullable=False),
        sa.Column('can_clock_others', sa.Boolean(), nullable=False),
        sa.Column('see_all_trucks', sa.Boolean(), nullable=False),
        sa.Column('edit_all_trucks', sa.Boolean(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_employee_brand'), 'employee', ['brand'], unique=False)

    op.create_table(
        'owner_security',
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('phones', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('backup_codes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('audit_log', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'auth_session',
        sa.Column('employee_id', sa.UUID(), nullable=False),
        sa.Column('device_id', sa.UUID(), nullable=True),
        sa.Column('active_brand', brand, nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['device_id'], ['device.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['employee_id'], ['employee.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_auth_session_employee_id'), 'auth_session', ['employee_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_auth_session_employee_id'), table_name='auth_session')
    op.drop_table('auth_session')
    op.drop_table('owner_security')
    op.drop_index(op.f('ix_employee_brand'), table_name='employee')
    op.drop_table('employee')
    op.drop_index(op.f('ix_device_brand'), table_name='device')
    op.drop_table('device')
    bind = op.get_bind()
    pay_type.drop(bind, checkfirst=True)
    device_type.drop(bind, checkfirst=True)
    brand.drop(bind, checkfirst=True)
