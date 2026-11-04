"""Add knowledge building tables for Stage 1.3

Revision ID: 026_knowledge_building
Revises: 025_embeddings_wiki
Create Date: 2026-10-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "026_knowledge_building"
down_revision = "025_embeddings_wiki"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create knowledge building schema."""

    # Table 1: extracted_facts - LLM-extracted structured facts
    op.create_table(
        "extracted_facts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("parsed_document_id", sa.String(64), sa.ForeignKey("parsed_documents.id"), nullable=False),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("fact_type", sa.String(50), nullable=False),  # role, activity, risk, metric, dependency
        sa.Column("fact_name", sa.String(255), nullable=False),  # Extracted fact name
        sa.Column("fact_value", sa.JSON(), nullable=True),  # Full fact structure
        sa.Column("confidence_score", sa.Float(), default=0.5),  # 0.0-1.0 confidence
        sa.Column("source_context", sa.String(500), nullable=True),  # Where it came from
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_extracted_facts_parsed_id", "extracted_facts", ["parsed_document_id"])
    op.create_index("ix_extracted_facts_project_id", "extracted_facts", ["project_id"])
    op.create_index("ix_extracted_facts_type", "extracted_facts", ["fact_type"])
    op.create_index("ix_extracted_facts_name", "extracted_facts", ["fact_name"])

    # Table 2: wiki_pages_draft - Wiki pages before deduplication
    op.create_table(
        "wiki_pages_draft",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("parsed_document_id", sa.String(64), sa.ForeignKey("parsed_documents.id"), nullable=False),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("entity_name", sa.String(255), nullable=False),  # What this page is about
        sa.Column("entity_type", sa.String(50), nullable=False),  # role, system, activity, etc.
        sa.Column("content", sa.Text(), nullable=False),  # Markdown wiki content
        sa.Column("source_facts", sa.JSON(), nullable=True),  # Facts used to generate
        sa.Column("is_deduplicated", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_wiki_draft_parsed_id", "wiki_pages_draft", ["parsed_document_id"])
    op.create_index("ix_wiki_draft_project_id", "wiki_pages_draft", ["project_id"])
    op.create_index("ix_wiki_draft_entity", "wiki_pages_draft", ["entity_name", "entity_type"])

    # Table 3: wiki_pages_final - Deduplicated wiki pages
    op.create_table(
        "wiki_pages_final",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("entity_name", sa.String(255), nullable=False),  # Canonical name
        sa.Column("entity_type", sa.String(50), nullable=False),  # role, system, etc.
        sa.Column("content", sa.Text(), nullable=False),  # Final wiki content
        sa.Column("aliases", sa.JSON(), nullable=True),  # Alternative names
        sa.Column("source_facts", sa.JSON(), nullable=True),  # All facts used
        sa.Column("merge_info", sa.JSON(), nullable=True),  # {is_canonical, merged_from, merge_count}
        sa.Column("is_published", sa.Boolean(), default=False),  # Ready for search
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_wiki_final_project_id", "wiki_pages_final", ["project_id"])
    op.create_index("ix_wiki_final_entity", "wiki_pages_final", ["entity_name"])
    op.create_index("ix_wiki_final_published", "wiki_pages_final", ["is_published"])
    op.create_index("ix_wiki_final_created", "wiki_pages_final", ["created_at"])

    # Table 4: embeddings_metadata - Tracking wiki page embeddings
    op.create_table(
        "embeddings_metadata",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("wiki_id", sa.String(64), sa.ForeignKey("wiki_pages_final.id"), nullable=False),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("embedding_model", sa.String(50), default="BAAI/bge-m3"),
        sa.Column("embedding_dimension", sa.Integer(), default=1024),
        sa.Column("qdrant_collection", sa.String(50), default="wiki_pages"),
        sa.Column("qdrant_point_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_embeddings_wiki_id", "embeddings_metadata", ["wiki_id"])
    op.create_index("ix_embeddings_project_id", "embeddings_metadata", ["project_id"])

    # Table 5: knowledge_metrics - Performance tracking
    op.create_table(
        "knowledge_metrics",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("extraction_duration_ms", sa.Integer(), nullable=True),
        sa.Column("wiki_generation_duration_ms", sa.Integer(), nullable=True),
        sa.Column("deduplication_duration_ms", sa.Integer(), nullable=True),
        sa.Column("total_facts_extracted", sa.Integer(), default=0),
        sa.Column("total_wiki_generated", sa.Integer(), default=0),
        sa.Column("total_wiki_final", sa.Integer(), default=0),
        sa.Column("duplicates_removed", sa.Integer(), default=0),
        sa.Column("failure_count", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_knowledge_metrics_project", "knowledge_metrics", ["project_id"])
    op.create_index("ix_knowledge_metrics_created", "knowledge_metrics", ["created_at"])


def downgrade() -> None:
    """Drop knowledge building schema."""

    # Drop metrics table
    op.drop_index("ix_knowledge_metrics_created", table_name="knowledge_metrics")
    op.drop_index("ix_knowledge_metrics_project", table_name="knowledge_metrics")
    op.drop_table("knowledge_metrics")

    # Drop embeddings metadata table
    op.drop_index("ix_embeddings_project_id", table_name="embeddings_metadata")
    op.drop_index("ix_embeddings_wiki_id", table_name="embeddings_metadata")
    op.drop_table("embeddings_metadata")

    # Drop final wiki pages table
    op.drop_index("ix_wiki_final_created", table_name="wiki_pages_final")
    op.drop_index("ix_wiki_final_published", table_name="wiki_pages_final")
    op.drop_index("ix_wiki_final_entity", table_name="wiki_pages_final")
    op.drop_index("ix_wiki_final_project_id", table_name="wiki_pages_final")
    op.drop_table("wiki_pages_final")

    # Drop draft wiki pages table
    op.drop_index("ix_wiki_draft_entity", table_name="wiki_pages_draft")
    op.drop_index("ix_wiki_draft_project_id", table_name="wiki_pages_draft")
    op.drop_index("ix_wiki_draft_parsed_id", table_name="wiki_pages_draft")
    op.drop_table("wiki_pages_draft")

    # Drop extracted facts table
    op.drop_index("ix_extracted_facts_name", table_name="extracted_facts")
    op.drop_index("ix_extracted_facts_type", table_name="extracted_facts")
    op.drop_index("ix_extracted_facts_project_id", table_name="extracted_facts")
    op.drop_index("ix_extracted_facts_parsed_id", table_name="extracted_facts")
    op.drop_table("extracted_facts")
