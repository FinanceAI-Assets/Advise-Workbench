"""Merge the workbench UI branch and the document ingestion branch.

Revision ID: 028_merge_heads
Revises: 023_workbench_ui, 027_error_handling
Create Date: 2026-10-23
"""

from __future__ import annotations

revision = "028_merge_heads"
down_revision = ("023_workbench_ui", "027_error_handling")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
