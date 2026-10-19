"""Versioned source-typed chunks, not embeddings or AI-generated descriptions."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evidence_chunks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("reader_version", sa.String(160), nullable=False),
        sa.Column("chunker_version", sa.String(40), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_metadata", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('prose','table_row','figure_caption')",
            name=op.f("ck_evidence_chunks_valid_kind"),
        ),
        sa.CheckConstraint(
            "page_number >= 1 AND page_number <= 300", name=op.f("ck_evidence_chunks_bounded_page")
        ),
    )
    op.create_index(
        "ix_chunk_document_reader",
        "evidence_chunks",
        ["document_id", "reader_version", "page_number"],
    )


def downgrade() -> None:
    op.drop_table("evidence_chunks")
