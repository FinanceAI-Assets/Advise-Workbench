"""Add document_jobs table for async processing

Revision ID: 022_document_jobs
Revises: 021_conversation_turns
Create Date: 2026-10-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "022_document_jobs"
down_revision = "021_conversation_turns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("job_id", sa.String(255), nullable=False, unique=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("parse_mode", sa.String(64), nullable=True),
        sa.Column("file_sha256", sa.String(64), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("failed_stage", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_document_jobs_job_id", "document_jobs", ["job_id"])
    op.create_index("ix_document_jobs_project_id", "document_jobs", ["project_id"])
    op.create_index("ix_document_jobs_user_id", "document_jobs", ["user_id"])
    op.create_index("ix_document_jobs_status", "document_jobs", ["status"])
    op.create_index("ix_document_jobs_created_at", "document_jobs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_document_jobs_created_at", table_name="document_jobs")
    op.drop_index("ix_document_jobs_status", table_name="document_jobs")
    op.drop_index("ix_document_jobs_user_id", table_name="document_jobs")
    op.drop_index("ix_document_jobs_project_id", table_name="document_jobs")
    op.drop_index("ix_document_jobs_job_id", table_name="document_jobs")
    op.drop_table("document_jobs")
