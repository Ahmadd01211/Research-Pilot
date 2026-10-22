"""Versioned Google embedding indexes with pgvector source vectors."""

import sqlalchemy as sa

from alembic import op
from app.infrastructure.database.vector_type import Vector768

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_indexes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("reader_version", sa.String(160), nullable=False),
        sa.Column("chunker_version", sa.String(40), nullable=False),
        sa.Column("provider", sa.String(24), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("format_version", sa.String(50), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatch_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_code", sa.String(40), nullable=True),
        sa.Column("processed_chunks", sa.Integer(), nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "document_id", "source_sha256", "reader_version", "chunker_version",
            "provider", "model", "dimensions", "format_version", name="uq_document_index_identity",
        ),
        sa.CheckConstraint(
            "state IN ('queued','processing','ready','failed','cancelled')",
            name=op.f("ck_document_indexes_valid_state"),
        ),
        sa.CheckConstraint("attempts >= 0 AND attempts <= 5", name=op.f("ck_document_indexes_bounded_attempts")),
    )
    op.create_index("ix_index_dispatch", "document_indexes", ["state", "dispatch_after"])
    op.create_table(
        "chunk_embeddings",
        sa.Column("index_id", sa.Uuid(), sa.ForeignKey("document_indexes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("chunk_id", sa.String(64), sa.ForeignKey("evidence_chunks.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("embedding", Vector768(), nullable=False),
    )
    op.create_index("ix_embedding_chunk", "chunk_embeddings", ["chunk_id"])


def downgrade() -> None:
    op.drop_index("ix_embedding_chunk", table_name="chunk_embeddings")
    op.drop_table("chunk_embeddings")
    op.drop_index("ix_index_dispatch", table_name="document_indexes")
    op.drop_table("document_indexes")
