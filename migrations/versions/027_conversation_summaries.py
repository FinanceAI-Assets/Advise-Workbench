"""Create conversation_summaries table (ONE per engagement) and update engagement_meta.

Revision ID: 027_conversation_summaries
Revises: 026_repair_user_role_schema
"""

from alembic import op
import sqlalchemy as sa

revision = "027_conversation_summaries"
down_revision = "026_repair_user_role_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create conversation_summaries table and add idle detection columns to engagement_meta."""

    # 1. Create conversation_summaries table (ONE per engagement)
    op.create_table(
        'conversation_summaries',
        sa.Column('id', sa.String(64), nullable=False),
        sa.Column('project_id', sa.String(64), nullable=False),
        sa.Column('summary_text', sa.Text(), nullable=False),
        sa.Column('summary_metadata_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('state_snapshot_json', sa.Text(), nullable=False),
        sa.Column('discovery_slots_snapshot', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('decision_answers_snapshot', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('conversation_fsm_state', sa.String(32), nullable=False),
        sa.Column('summary_trigger', sa.String(32), nullable=False),
        sa.Column('idle_duration_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('restored_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', name='uq_conversation_summaries_project_id')
    )
    op.create_index('ix_conversation_summaries_project_id', 'conversation_summaries', ['project_id'], unique=False)

    # 2. Add idle detection columns to engagement_meta
    op.add_column('engagement_meta', sa.Column('engagement_session_id', sa.String(64), nullable=True))
    op.add_column('engagement_meta', sa.Column('last_activity_at', sa.DateTime(), nullable=True))
    op.add_column('engagement_meta', sa.Column('idle_timeout_seconds', sa.Integer(), nullable=False, server_default='600'))
    op.add_column('engagement_meta', sa.Column('enable_idle_detection', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    """Rollback migration."""

    # 1. Drop idle detection columns from engagement_meta
    op.drop_column('engagement_meta', 'enable_idle_detection')
    op.drop_column('engagement_meta', 'idle_timeout_seconds')
    op.drop_column('engagement_meta', 'last_activity_at')
    op.drop_column('engagement_meta', 'engagement_session_id')

    # 2. Drop conversation_summaries table
    op.drop_index('ix_conversation_summaries_project_id', table_name='conversation_summaries')
    op.drop_table('conversation_summaries')
