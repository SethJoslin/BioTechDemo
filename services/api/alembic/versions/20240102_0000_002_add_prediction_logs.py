"""Add prediction logs table for model monitoring

Revision ID: 002
Revises: 001
Create Date: 2024-01-02

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    """Create prediction_logs table for model performance monitoring."""
    op.create_table(
        'prediction_logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_id', sa.String(), nullable=True),
        sa.Column('model_version', sa.String(), nullable=False),
        sa.Column('input_features', sa.Text(), nullable=False),
        sa.Column('prediction', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('latency_ms', sa.Float(), nullable=False),
        sa.Column('endpoint', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create index on timestamp for efficient time-range queries
    op.create_index('ix_prediction_logs_timestamp', 'prediction_logs', ['timestamp'])

    # Create index on model_version for filtering by version
    op.create_index('ix_prediction_logs_model_version', 'prediction_logs', ['model_version'])


def downgrade():
    """Drop prediction_logs table."""
    op.drop_index('ix_prediction_logs_model_version', table_name='prediction_logs')
    op.drop_index('ix_prediction_logs_timestamp', table_name='prediction_logs')
    op.drop_table('prediction_logs')
