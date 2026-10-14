"""add engagement_meta for additive engagement list/detail metadata

Revision ID: 022_engagement_meta
Revises: 021_conversation_turns
Create Date: 2026-10-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "022_engagement_meta"
down_revision = "021_conversation_turns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "engagement_meta",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("code", sa.String(32), nullable=True),
        sa.Column("type", sa.String(64), nullable=True),
        sa.Column("stage", sa.String(32), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=True),
        sa.Column("next_task", sa.Text(), nullable=True),
        sa.Column("due_date", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_engagement_meta_project_id", "engagement_meta", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_engagement_meta_project_id", table_name="engagement_meta")
    op.drop_table("engagement_meta")
