"""owner_security recovery emails column

Revision ID: b8e4f2a1c9d3
Revises: 206c2604ac57
Create Date: 2026-07-14 21:05:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b8e4f2a1c9d3'
down_revision: Union[str, None] = '206c2604ac57'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Owner 2FA email destinations (recovery channel alongside `phones`). server_default
    # backfills the single existing owner_security row to an empty list; the ORM sets it
    # explicitly on new rows (default=list).
    op.add_column(
        'owner_security',
        sa.Column('emails', postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column('owner_security', 'emails')
