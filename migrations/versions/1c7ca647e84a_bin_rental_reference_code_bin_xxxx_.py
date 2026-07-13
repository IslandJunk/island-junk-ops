"""bin rental reference_code (BIN-xxxx) + reminder ref

Revision ID: 1c7ca647e84a
Revises: bb14991c2fcc
Create Date: 2026-07-12 19:04:23.497698
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c7ca647e84a'
down_revision: Union[str, None] = 'bb14991c2fcc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Human-readable rental codes BIN-4001, BIN-4002, ... — GLOBAL (not per-brand) so a code is
    # unambiguous as the QuickBooks match key the owner pastes into the invoice PO field.
    op.execute("CREATE SEQUENCE IF NOT EXISTS bin_ref_seq START WITH 4001")

    op.add_column('bin', sa.Column('reference_code', sa.String(length=20), nullable=True))
    op.add_column('bin', sa.Column('rental_group_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_bin_reference_code'), 'bin', ['reference_code'], unique=False)

    op.add_column('reminder', sa.Column('reference_code', sa.String(length=20), nullable=True))
    op.create_index(op.f('ix_reminder_reference_code'), 'reminder', ['reference_code'], unique=False)

    # Backfill: bins currently OUT (dropped/full) get a code now so the owner queue never shows a
    # blank for an in-flight rental. Idle/in-yard bins get theirs at their next drop.
    op.execute(
        "UPDATE bin SET reference_code = 'BIN-' || nextval('bin_ref_seq') "
        "WHERE status IN ('dropped','full') AND reference_code IS NULL"
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_reminder_reference_code'), table_name='reminder')
    op.drop_column('reminder', 'reference_code')
    op.drop_index(op.f('ix_bin_reference_code'), table_name='bin')
    op.drop_column('bin', 'rental_group_id')
    op.drop_column('bin', 'reference_code')
    op.execute("DROP SEQUENCE IF EXISTS bin_ref_seq")
