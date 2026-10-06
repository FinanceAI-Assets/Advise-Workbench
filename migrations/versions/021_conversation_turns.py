"""add conversation_turns for conversation messages answered in the background

Revision ID: 021_conversation_turns
Revises: 020_run_tasks_per_run_key
Create Date: 2026-10-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "021_conversation_turns"
down_revision = "020_run_tasks_per_run_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_turns",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("phase", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("status_code", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("response_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_conversation_turns_project_id", "conversation_turns", ["project_id"])
    op.create_index("ix_conversation_turns_user_id", "conversation_turns", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_conversation_turns_user_id", table_name="conversation_turns")
    op.drop_index("ix_conversation_turns_project_id", table_name="conversation_turns")
    op.drop_table("conversation_turns")
