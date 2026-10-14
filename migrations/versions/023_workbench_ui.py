"""workbench UI: user profile, engagement brief, reviews, notifications, practice catalog, seeded records

Revision ID: 023_workbench_ui
Revises: 022_engagement_meta
Create Date: 2026-10-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "023_workbench_ui"
down_revision = "022_engagement_meta"
branch_labels = None
depends_on = None

_USER_COLUMNS = (
    ("full_name", sa.String(255)),
    ("job_title", sa.String(128)),
    ("is_admin", sa.Boolean()),
)
_META_COLUMNS = (
    ("client_org", sa.String(255)),
    ("brief", sa.Text()),
    ("sponsor_objective", sa.Text()),
    ("scope", sa.Text()),
    ("success_measures", sa.Text()),
    ("start_date", sa.String(32)),
    ("target_close", sa.String(32)),
    ("classification", sa.String(64)),
    ("retention_days", sa.Integer()),
    ("status", sa.String(16)),
)
_NEW_TABLES = (
    "workbench_records",
    "saved_practices",
    "lp_practices",
    "notifications",
    "review_comments",
    "reviews",
    "activity_events",
)


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        for name, col_type in _USER_COLUMNS:
            batch_op.add_column(sa.Column(name, col_type, nullable=True))
    with op.batch_alter_table("engagement_meta") as batch_op:
        for name, col_type in _META_COLUMNS:
            batch_op.add_column(sa.Column(name, col_type, nullable=True))
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.add_column(sa.Column("skill_id", sa.String(64), nullable=True))

    op.create_table(
        "activity_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_activity_events_project_id", "activity_events", ["project_id"])
    op.create_index("ix_activity_events_created_at", "activity_events", ["created_at"])

    op.create_table(
        "reviews",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("run_id", sa.String(64), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("artifact_type", sa.String(32), nullable=False),
        sa.Column("version_label", sa.String(64), nullable=False, server_default=""),
        sa.Column("owner_id", sa.String(64), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewer_id", sa.String(64), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("due_date", sa.String(32), nullable=False, server_default=""),
        sa.Column("state", sa.String(32), nullable=False, server_default="Awaiting review"),
        sa.Column("risk", sa.String(32), nullable=False, server_default=""),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_reviews_project_id", "reviews", ["project_id"])
    op.create_index("ix_reviews_reviewer_id", "reviews", ["reviewer_id"])

    op.create_table(
        "review_comments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("review_id", sa.String(64), sa.ForeignKey("reviews.id"), nullable=False),
        sa.Column("author", sa.String(255), nullable=False),
        sa.Column("title", sa.String(255), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("anchor", sa.String(64), nullable=False, server_default=""),
        sa.Column("status", sa.String(16), nullable=False, server_default="Open"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_review_comments_review_id", "review_comments", ["review_id"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("link", sa.String(255), nullable=False, server_default=""),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])

    op.create_table(
        "lp_practices",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("maturity", sa.String(32), nullable=False, server_default=""),
        sa.Column("version_label", sa.String(32), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="Approved"),
        sa.Column("owner", sa.String(255), nullable=False, server_default=""),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_lp_practices_category", "lp_practices", ["category"])

    op.create_table(
        "saved_practices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("practice_id", sa.String(64), sa.ForeignKey("lp_practices.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "practice_id", name="uq_saved_practices_user_practice"),
    )
    op.create_index("ix_saved_practices_user_id", "saved_practices", ["user_id"])

    op.create_table(
        "workbench_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("collection", sa.String(64), nullable=False),
        sa.Column("record_id", sa.String(64), nullable=False),
        sa.Column("project_id", sa.String(64), nullable=True),
        sa.Column("user_id", sa.String(64), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("collection", "record_id", name="uq_workbench_records_collection_record"),
    )
    op.create_index("ix_workbench_records_collection", "workbench_records", ["collection"])
    op.create_index("ix_workbench_records_project_id", "workbench_records", ["project_id"])
    op.create_index("ix_workbench_records_user_id", "workbench_records", ["user_id"])


def downgrade() -> None:
    for table in _NEW_TABLES:
        op.drop_table(table)
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.drop_column("skill_id")
    with op.batch_alter_table("engagement_meta") as batch_op:
        for name, _ in reversed(_META_COLUMNS):
            batch_op.drop_column(name)
    with op.batch_alter_table("users") as batch_op:
        for name, _ in reversed(_USER_COLUMNS):
            batch_op.drop_column(name)
