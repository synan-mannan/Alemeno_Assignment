"""initial migration

Revision ID: 0001
Revises: None
Create Date: 2026-06-09 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create jobs table
    op.create_table(
        'jobs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('progress', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('filesize', sa.Integer(), nullable=False),
        sa.Column('raw_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_jobs_status'), 'jobs', ['status'], unique=False)

    # Create transactions table
    op.create_table(
        'transactions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=False),
        sa.Column('txn_id', sa.String(), nullable=True),
        sa.Column('original_txn_id', sa.String(), nullable=True),
        sa.Column('date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('original_date', sa.String(), nullable=True),
        sa.Column('merchant', sa.String(), nullable=True),
        sa.Column('original_merchant', sa.String(), nullable=True),
        sa.Column('amount', sa.Float(), nullable=True),
        sa.Column('original_amount', sa.String(), nullable=True),
        sa.Column('currency', sa.String(), nullable=True),
        sa.Column('original_currency', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('original_status', sa.String(), nullable=True),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('original_category', sa.String(), nullable=True),
        sa.Column('account_id', sa.String(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('original_notes', sa.Text(), nullable=True),
        sa.Column('is_anomaly', sa.Boolean(), nullable=False),
        sa.Column('anomalies', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('cleaning_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transactions_account_id'), 'transactions', ['account_id'], unique=False)
    op.create_index(op.f('ix_transactions_is_anomaly'), 'transactions', ['is_anomaly'], unique=False)
    op.create_index(op.f('ix_transactions_job_id'), 'transactions', ['job_id'], unique=False)
    op.create_index(op.f('ix_transactions_txn_id'), 'transactions', ['txn_id'], unique=False)

    # Create job_summaries table
    op.create_table(
        'job_summaries',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=False),
        sa.Column('total_spend', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('top_merchants', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('anomaly_count', sa.Integer(), nullable=False),
        sa.Column('financial_narrative', sa.Text(), nullable=True),
        sa.Column('risk_level', sa.String(), nullable=False),
        sa.Column('token_usage', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_job_summaries_job_id'), 'job_summaries', ['job_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_job_summaries_job_id'), table_name='job_summaries')
    op.drop_table('job_summaries')
    op.drop_index(op.f('ix_transactions_txn_id'), table_name='transactions')
    op.drop_index(op.f('ix_transactions_job_id'), table_name='transactions')
    op.drop_index(op.f('ix_transactions_is_anomaly'), table_name='transactions')
    op.drop_index(op.f('ix_transactions_account_id'), table_name='transactions')
    op.drop_table('transactions')
    op.drop_index(op.f('ix_jobs_status'), table_name='jobs')
    op.drop_table('jobs')
