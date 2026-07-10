"""maintenance reminders defect_flag

Revision ID: 46d1bfdb249d
Revises: 4cd57b8ea105
Create Date: 2026-07-09 20:59:00.553697
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '46d1bfdb249d'
down_revision: Union[str, None] = '4cd57b8ea105'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# `brand` already exists -> reference it (don't re-create). `reminder_kind` is new.
brand = postgresql.ENUM('victoria', 'nanaimo', name='brand', create_type=False)
reminder_kind = postgresql.ENUM('general', 'cc_charge', 'booking_draft',
                                name='reminder_kind', create_type=False)


def upgrade() -> None:
    reminder_kind.create(op.get_bind(), checkfirst=True)   # new enum, create once

    op.create_table('maintenance_doc',
        sa.Column('doc', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('brand', brand, nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('brand', name='uq_maintenance_doc_brand'),
    )
    op.create_index(op.f('ix_maintenance_doc_brand'), 'maintenance_doc', ['brand'], unique=False)

    op.create_table('defect_flag',
        sa.Column('source_id', sa.String(length=60), nullable=True),
        sa.Column('truck', sa.String(length=60), nullable=True),
        sa.Column('item', sa.String(length=180), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('who', sa.String(length=120), nullable=True),
        sa.Column('flag_date', sa.String(length=20), nullable=True),
        sa.Column('source', sa.String(length=40), nullable=True),
        sa.Column('open', sa.Boolean(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('brand', brand, nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('brand', 'source_id', name='uq_defect_flag_brand_source'),
    )
    op.create_index(op.f('ix_defect_flag_brand'), 'defect_flag', ['brand'], unique=False)
    op.create_index(op.f('ix_defect_flag_source_id'), 'defect_flag', ['source_id'], unique=False)

    op.create_table('reminder',
        sa.Column('source_id', sa.String(length=60), nullable=True),
        sa.Column('kind', reminder_kind, nullable=False),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('by', sa.String(length=120), nullable=True),
        sa.Column('ts', sa.BigInteger(), nullable=True),
        sa.Column('due', sa.Date(), nullable=True),
        sa.Column('done', sa.Boolean(), nullable=False),
        sa.Column('booking', sa.Boolean(), nullable=False),
        sa.Column('name', sa.String(length=180), nullable=True),
        sa.Column('addr', sa.String(length=255), nullable=True),
        sa.Column('draft', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('calendar', sa.String(length=120), nullable=True),
        sa.Column('job_id', sa.UUID(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('brand', brand, nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['job.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('brand', 'source_id', name='uq_reminder_brand_source'),
    )
    op.create_index(op.f('ix_reminder_brand'), 'reminder', ['brand'], unique=False)
    op.create_index(op.f('ix_reminder_source_id'), 'reminder', ['source_id'], unique=False)
    op.create_index(op.f('ix_reminder_job_id'), 'reminder', ['job_id'], unique=False)


def downgrade() -> None:
    op.drop_table('reminder')
    op.drop_table('defect_flag')
    op.drop_index(op.f('ix_maintenance_doc_brand'), table_name='maintenance_doc')
    op.drop_table('maintenance_doc')
    reminder_kind.drop(op.get_bind(), checkfirst=True)
