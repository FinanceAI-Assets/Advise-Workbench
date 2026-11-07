"""Merge the conversation-summaries branch into the main migration chain.

Revision ID: 031_merge_conversation_summary_head
Revises: 027_conversation_summaries, 030_document_chunk_links
"""
from __future__ import annotations

revision = "031_merge_conversation_summary_head"
down_revision = ("027_conversation_summaries", "030_document_chunk_links")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Merge only; no schema change."""


def downgrade() -> None:
    """Merge only; no schema change."""
