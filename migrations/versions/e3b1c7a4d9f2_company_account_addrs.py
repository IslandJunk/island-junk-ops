"""company_customer.account_addrs (saved location -> that site's job address)

Additive to the existing `accounts` string array (which stays the plain location-name list every
other reader uses). This map lets picking a saved commercial location auto-fill the address the
crew drive to, instead of the manager retyping the job site on every booking.

Revision ID: e3b1c7a4d9f2
Revises: d7a3f9c2e1b8
Create Date: 2026-07-23 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e3b1c7a4d9f2'
down_revision: Union[str, None] = 'd7a3f9c2e1b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'company_customer',
        sa.Column(
            'account_addrs',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('company_customer', 'account_addrs')
