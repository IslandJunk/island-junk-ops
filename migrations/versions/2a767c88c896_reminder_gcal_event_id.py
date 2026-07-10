"""reminder gcal_event_id

Revision ID: 2a767c88c896
Revises: 46d1bfdb249d
Create Date: 2026-07-09 21:56:20.233769
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a767c88c896'
down_revision: Union[str, None] = '46d1bfdb249d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('reminder', sa.Column('gcal_event_id', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('reminder', 'gcal_event_id')
