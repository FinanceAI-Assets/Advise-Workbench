"""Passages are stored once per unique text; document_chunk_links maps each document version to its passages.

Revision ID: 030_document_chunk_links
Revises: 029_ingestion_scope, 029_merge_role_heads
Create Date: 2026-10-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "030_document_chunk_links"
down_revision = ("029_ingestion_scope", "029_merge_role_heads")  # also merges the role-migration branch
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_chunk_links",
        sa.Column("document_file_id", sa.String(64), primary_key=True),
        sa.Column("chunk_number", sa.Integer(), primary_key=True),
        sa.Column("chunk_id", sa.String(64), sa.ForeignKey("chunk_archive.id"), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("reused", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_document_chunk_links_chunk", "document_chunk_links", ["chunk_id"])
    op.create_index("ix_document_chunk_links_document", "document_chunk_links", ["document_file_id"])


def downgrade() -> None:
    op.drop_index("ix_document_chunk_links_document", table_name="document_chunk_links")
    op.drop_index("ix_document_chunk_links_chunk", table_name="document_chunk_links")
    op.drop_table("document_chunk_links")
