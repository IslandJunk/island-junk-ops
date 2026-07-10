"""colour map

Revision ID: 980268b91d57
Revises: 2263e99c12d8
Create Date: 2026-07-09 07:37:55.492806
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '980268b91d57'
down_revision: Union[str, None] = '2263e99c12d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# `brand` already exists (initial migration) -> reference it, don't re-create.
brand = postgresql.ENUM('victoria', 'nanaimo', name='brand', create_type=False)
# `colour_kind` is new -> create once (checkfirst), columns reference create_type=False.
colour_kind = postgresql.ENUM('assignable', 'status', 'unassigned', name='colour_kind', create_type=False)


def upgrade() -> None:
    colour_kind.create(op.get_bind(), checkfirst=True)
    op.create_table(
        'colour_map',
        sa.Column('key', sa.String(length=40), nullable=False),
        sa.Column('name', sa.String(length=60), nullable=False),
        sa.Column('google_color_id', sa.Integer(), nullable=True),
        sa.Column('hex', sa.String(length=7), nullable=True),
        sa.Column('kind', colour_kind, nullable=False),
        sa.Column('status_meaning', sa.String(length=120), nullable=True),
        sa.Column('assigned_truck', sa.String(length=20), nullable=True),
        sa.Column('is_custom', sa.Boolean(), nullable=False),
        sa.Column('is_locked', sa.Boolean(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('brand', brand, nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('brand', 'key', name='uq_colour_map_brand_key'),
    )
    op.create_index(op.f('ix_colour_map_brand'), 'colour_map', ['brand'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_colour_map_brand'), table_name='colour_map')
    op.drop_table('colour_map')
    colour_kind.drop(op.get_bind(), checkfirst=True)
