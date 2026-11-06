"""Add evaluation_passed flag to runs table for Visual QA tracking

Revision ID: 024_evaluation_passed
Revises: 023_workbench_ui
Create Date: 2026-11-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "024_evaluation_passed"
down_revision = "023_workbench_ui"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add evaluation_passed column to runs table."""
    with op.batch_alter_table("runs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "evaluation_passed",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    """Remove evaluation_passed column from runs table."""
    with op.batch_alter_table("runs") as batch_op:
        batch_op.drop_column("evaluation_passed")
