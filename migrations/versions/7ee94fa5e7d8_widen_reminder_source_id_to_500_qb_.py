"""widen reminder.source_id to 500 (QB customer name+addr)

Revision ID: 7ee94fa5e7d8
Revises: 1c7ca647e84a
Create Date: 2026-07-12 19:40:15.359450
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7ee94fa5e7d8'
down_revision: Union[str, None] = '1c7ca647e84a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # cc_charge source_id is "cc:{name}|{addr}|{date}" — a QB customer name + full billing
    # address overflowed varchar(60). Widen to comfortably fit name(180)+addr(255)+date.
    op.alter_column('reminder', 'source_id', existing_type=sa.String(length=60),
                    type_=sa.String(length=500), existing_nullable=True)


def downgrade() -> None:
    op.alter_column('reminder', 'source_id', existing_type=sa.String(length=500),
                    type_=sa.String(length=60), existing_nullable=True)
