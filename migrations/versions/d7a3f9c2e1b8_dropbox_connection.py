"""dropbox_connection (OAuth link to Wes's Dropbox account)

Revision ID: d7a3f9c2e1b8
Revises: c4d9e1a2b3f5
Create Date: 2026-07-14 22:45:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7a3f9c2e1b8'
down_revision: Union[str, None] = 'c4d9e1a2b3f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'dropbox_connection',
        sa.Column('account_name', sa.String(length=200), nullable=True),
        sa.Column('account_email', sa.String(length=200), nullable=True),
        sa.Column('access_token', sa.Text(), nullable=True),           # Fernet-encrypted at rest
        sa.Column('access_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('refresh_token', sa.Text(), nullable=True),          # Fernet-encrypted at rest
        sa.Column('connected_by', sa.String(length=120), nullable=True),
        sa.Column('active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('dropbox_connection')
