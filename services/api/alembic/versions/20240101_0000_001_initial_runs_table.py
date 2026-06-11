"""Initial runs table creation.

Revision ID: 001
Revises: None
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the runs table."""
    op.create_table(
        "runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("metadata", sa.Text(), server_default="{}"),
        sa.Column("qc_status", sa.String(), server_default="unknown"),
        sa.Column("qc_metrics", sa.Text(), server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # Create index on created_at for efficient sorting
    op.create_index("ix_runs_created_at", "runs", ["created_at"])


def downgrade() -> None:
    """Drop the runs table."""
    op.drop_index("ix_runs_created_at", table_name="runs")
    op.drop_table("runs")
