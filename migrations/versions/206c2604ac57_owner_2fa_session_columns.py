"""owner 2fa session columns

Revision ID: 206c2604ac57
Revises: 7ee94fa5e7d8
Create Date: 2026-07-14 19:54:19.977299
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '206c2604ac57'
down_revision: Union[str, None] = '7ee94fa5e7d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Owner SMS 2FA state, on the session. server_default backfills existing rows to "not verified".
    op.add_column('auth_session', sa.Column('owner_2fa_verified', sa.Boolean(),
                  nullable=False, server_default=sa.false()))
    op.add_column('auth_session', sa.Column('twofa_code_hash', sa.String(length=255), nullable=True))
    op.add_column('auth_session', sa.Column('twofa_expires_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('auth_session', 'twofa_expires_at')
    op.drop_column('auth_session', 'twofa_code_hash')
    op.drop_column('auth_session', 'owner_2fa_verified')
