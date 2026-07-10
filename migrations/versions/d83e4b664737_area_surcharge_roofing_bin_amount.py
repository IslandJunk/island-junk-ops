"""area_surcharge roofing_bin_amount

Revision ID: d83e4b664737
Revises: 2a767c88c896
Create Date: 2026-07-09 23:03:12.981689
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd83e4b664737'
down_revision: Union[str, None] = '2a767c88c896'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('area_surcharge', sa.Column('roofing_bin_amount', sa.Numeric(precision=10, scale=2), nullable=True))


def downgrade() -> None:
    op.drop_column('area_surcharge', 'roofing_bin_amount')
