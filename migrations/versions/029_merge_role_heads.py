"""Merge the user role branch and the merged ingestion branch.

Revision ID: 029_merge_role_heads
Revises: 026_repair_user_role_schema, 028_merge_heads
Create Date: 2026-10-26
"""

from __future__ import annotations

revision = "029_merge_role_heads"
down_revision = ("026_repair_user_role_schema", "028_merge_heads")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
