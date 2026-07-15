"""job_photo table (reference photos attached to a Job)

Revision ID: c4d9e1a2b3f5
Revises: b8e4f2a1c9d3
Create Date: 2026-07-14 22:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d9e1a2b3f5'
down_revision: Union[str, None] = 'b8e4f2a1c9d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'job_photo',
        sa.Column('job_id', sa.UUID(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('content_type', sa.String(length=80), server_default='image/jpeg', nullable=False),
        sa.Column('data', sa.LargeBinary(), nullable=False),
        sa.Column('uploaded_by', sa.String(length=120), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['job.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_job_photo_job_id'), 'job_photo', ['job_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_job_photo_job_id'), table_name='job_photo')
    op.drop_table('job_photo')
