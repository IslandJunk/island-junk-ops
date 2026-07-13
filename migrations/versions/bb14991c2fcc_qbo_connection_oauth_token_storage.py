"""qbo_connection oauth token storage

Revision ID: bb14991c2fcc
Revises: 28c686247d41
Create Date: 2026-07-12 17:43:23.965118
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# The shared `brand` enum already exists (created by the initial migration). Reference it
# WITHOUT re-creating the type (create_type=False) — standing gotcha, PROGRESS.md §5.
brand_enum = postgresql.ENUM('victoria', 'nanaimo', name='brand', create_type=False)


# revision identifiers, used by Alembic.
revision: str = 'bb14991c2fcc'
down_revision: Union[str, None] = '28c686247d41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'qbo_connection',
        sa.Column('realm_id', sa.String(length=32), nullable=False),
        sa.Column('company_name', sa.String(length=200), nullable=True),
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('access_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('refresh_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('auto_sync_enabled', sa.Boolean(), nullable=False),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('connected_by', sa.String(length=120), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('brand', brand_enum, nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_qbo_connection_brand'), 'qbo_connection', ['brand'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_qbo_connection_brand'), table_name='qbo_connection')
    op.drop_table('qbo_connection')
