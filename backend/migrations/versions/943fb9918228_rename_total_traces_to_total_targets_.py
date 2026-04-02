"""rename total_traces to total_targets and drop monitoring_request_count

Revision ID: 943fb9918228
Revises: 3ca3dee4b44a
Create Date: 2026-04-02 11:45:38.941248
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '943fb9918228'
down_revision: Union[str, None] = '3ca3dee4b44a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('eval_runs', 'total_traces', new_column_name='total_targets')
    op.drop_column('usage_records', 'monitoring_request_count')


def downgrade() -> None:
    op.add_column(
        'usage_records',
        sa.Column('monitoring_request_count', sa.INTEGER(), server_default='0', nullable=False),
    )
    op.alter_column('eval_runs', 'total_targets', new_column_name='total_traces')
