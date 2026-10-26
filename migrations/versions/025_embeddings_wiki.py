"""Add embeddings and wiki tables for Stage 1.3

Revision ID: 025_embeddings_wiki
Revises: 024_document_parsing
Create Date: 2026-10-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "025_embeddings_wiki"
down_revision = "024_document_parsing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create embeddings and wiki schema."""

    # Table 1: chunk_embeddings - Vector embeddings for semantic search
    op.create_table(
        "chunk_embeddings",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("chunk_id", sa.String(64), sa.ForeignKey("chunk_archive.id"), nullable=False),
        sa.Column("document_file_id", sa.String(64), sa.ForeignKey("document_files.id"), nullable=False),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),  # 1024-dimensional vector
        sa.Column("embedding_dimension", sa.Integer(), default=1024),
        sa.Column("model_name", sa.String(50), default="BAAI/bge-m3"),
        sa.Column("qdrant_point_id", sa.String(64), nullable=True),  # Qdrant reference
        sa.Column("embedding_generated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_chunk_embeddings_chunk_id", "chunk_embeddings", ["chunk_id"])
    op.create_index("ix_chunk_embeddings_file_id", "chunk_embeddings", ["document_file_id"])
    op.create_index("ix_chunk_embeddings_project_id", "chunk_embeddings", ["project_id"])

    # Table 2: embedding_metrics - Performance tracking for embeddings
    op.create_table(
        "embedding_metrics",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("embedding_duration_ms", sa.Integer(), nullable=True),
        sa.Column("wiki_generation_duration_ms", sa.Integer(), nullable=True),
        sa.Column("total_chunks_embedded", sa.Integer(), default=0),
        sa.Column("total_wiki_pages_created", sa.Integer(), default=0),
        sa.Column("embedding_model", sa.String(50), default="BAAI/bge-m3"),
        sa.Column("qdrant_collection_size", sa.Integer(), nullable=True),
        sa.Column("failure_count", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_embedding_metrics_project", "embedding_metrics", ["project_id"])
    op.create_index("ix_embedding_metrics_created", "embedding_metrics", ["created_at"])


def downgrade() -> None:
    """Drop embeddings and wiki schema."""

    # Drop metrics table
    op.drop_index("ix_embedding_metrics_created", table_name="embedding_metrics")
    op.drop_index("ix_embedding_metrics_project", table_name="embedding_metrics")
    op.drop_table("embedding_metrics")

    # Drop embeddings table
    op.drop_index("ix_chunk_embeddings_project_id", table_name="chunk_embeddings")
    op.drop_index("ix_chunk_embeddings_file_id", table_name="chunk_embeddings")
    op.drop_index("ix_chunk_embeddings_chunk_id", table_name="chunk_embeddings")
    op.drop_table("chunk_embeddings")
