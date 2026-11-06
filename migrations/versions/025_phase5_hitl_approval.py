"""Add Phase 5 HITL approval tracking - ArtifactApprovalRecord and Run phase_5 fields

Revision ID: 025_phase5_hitl_approval
Revises: 024_evaluation_passed
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "025_phase5_hitl_approval"
down_revision = "024_evaluation_passed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add Phase 5 HITL approval tracking."""

    # Add Phase 5 fields to runs table
    with op.batch_alter_table("runs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "phase_5_status",
                sa.String(32),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "phase_5_started_at",
                sa.DateTime(),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "phase_5_approval_data",
                sa.Text(),
                nullable=False,
                server_default="{}",
            )
        )

    # Create artifact_approvals table
    op.create_table(
        "artifact_approvals",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("artifact_type", sa.String(32), nullable=False),
        sa.Column("version", sa.String(8), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_immutable", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("total_slides", sa.Integer(), nullable=True),
        sa.Column("approved_slides", sa.Text(), nullable=True, server_default="[]"),
        sa.Column("rejected_slides", sa.Text(), nullable=True, server_default="[]"),
        sa.Column("user_feedback", sa.Text(), nullable=True),
        sa.Column("rejected_by", sa.String(64), nullable=True),
        sa.Column("rejected_at", sa.DateTime(), nullable=True),
        sa.Column("replaced_by", sa.String(8), nullable=True),
        sa.Column("replaced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes on artifact_approvals
    op.create_index(
        "ix_artifact_approvals_run_artifact",
        "artifact_approvals",
        ["run_id", "artifact_type"],
    )
    op.create_index(
        "ix_artifact_approvals_run_current",
        "artifact_approvals",
        ["run_id", "is_current"],
    )
    op.create_index(
        "ix_artifact_approvals_created_at",
        "artifact_approvals",
        ["created_at"],
    )


def downgrade() -> None:
    """Remove Phase 5 HITL approval tracking."""

    # Drop artifact_approvals table
    op.drop_index("ix_artifact_approvals_created_at", table_name="artifact_approvals")
    op.drop_index("ix_artifact_approvals_run_current", table_name="artifact_approvals")
    op.drop_index("ix_artifact_approvals_run_artifact", table_name="artifact_approvals")
    op.drop_table("artifact_approvals")

    # Remove Phase 5 fields from runs table
    with op.batch_alter_table("runs") as batch_op:
        batch_op.drop_column("phase_5_approval_data")
        batch_op.drop_column("phase_5_started_at")
        batch_op.drop_column("phase_5_status")
