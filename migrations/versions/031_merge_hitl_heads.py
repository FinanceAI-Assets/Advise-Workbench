"""Merge the Phase 5 HITL branch and the document ingestion / role branch.

Revision ID: 031_merge_hitl_heads
Revises: 030_document_chunk_links, 025_phase5_hitl_approval
Create Date: 2026-11-06
"""

from __future__ import annotations

revision = "031_merge_hitl_heads"
down_revision = ("030_document_chunk_links", "025_phase5_hitl_approval")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
