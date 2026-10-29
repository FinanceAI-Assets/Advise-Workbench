"""Add TaskFailure and Notification tables for error handling.

Revision ID: 027_error_handling
Revises: 026_knowledge_building
Create Date: 2026-10-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "027_error_handling"
down_revision = "026_knowledge_building"
branch_labels = None
depends_on = None


def upgrade():
    """Create error handling tables."""
    op.create_table(
        "task_failures",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("task_name", sa.String(100), nullable=False),
        sa.Column("document_file_id", sa.String(64), nullable=False),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("error_message", sa.String(500), nullable=False),
        sa.Column("error_type", sa.String(100), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("is_final_failure", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_task_failures_document", "document_file_id"),
        sa.Index("ix_task_failures_project", "project_id"),
        sa.Index("ix_task_failures_task", "task_name"),
        sa.Index("ix_task_failures_error_type", "error_type"),
        sa.Index("ix_task_failures_created", "created_at"),
    )

    op.create_table(
        "in_app_notifications",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("document_file_id", sa.String(64), nullable=True),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_in_app_notifications_user", "user_id"),
        sa.Index("ix_in_app_notifications_project", "project_id"),
        sa.Index("ix_in_app_notifications_type", "notification_type"),
        sa.Index("ix_in_app_notifications_created", "created_at"),
    )

    op.create_table(
        "task_failure_metrics",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("total_failures", sa.Integer(), nullable=False),
        sa.Column("final_failures", sa.Integer(), nullable=False),
        sa.Column("by_task", sa.JSON(), nullable=True),
        sa.Column("by_error_type", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_task_failure_metrics_project", "project_id"),
        sa.Index("ix_task_failure_metrics_created", "created_at"),
    )


def downgrade():
    """Drop error handling tables."""
    op.drop_index("ix_task_failure_metrics_created", table_name="task_failure_metrics")
    op.drop_index("ix_task_failure_metrics_project", table_name="task_failure_metrics")
    op.drop_table("task_failure_metrics")

    op.drop_index("ix_in_app_notifications_created", table_name="in_app_notifications")
    op.drop_index("ix_in_app_notifications_type", table_name="in_app_notifications")
    op.drop_index("ix_in_app_notifications_project", table_name="in_app_notifications")
    op.drop_index("ix_in_app_notifications_user", table_name="in_app_notifications")
    op.drop_table("in_app_notifications")

    op.drop_index("ix_task_failures_created", table_name="task_failures")
    op.drop_index("ix_task_failures_error_type", table_name="task_failures")
    op.drop_index("ix_task_failures_task", table_name="task_failures")
    op.drop_index("ix_task_failures_project", table_name="task_failures")
    op.drop_index("ix_task_failures_document", table_name="task_failures")
    op.drop_table("task_failures")
