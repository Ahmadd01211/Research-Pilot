"""Durable source-linked literature matrix rows and cells."""

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "literature_matrix_rows",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("research_projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("revision >= 1", name=op.f("ck_literature_matrix_rows_positive_revision")),
    )
    op.create_index("ix_matrix_project_created", "literature_matrix_rows", ["project_id", "created_at", "id"])
    op.create_table(
        "literature_matrix_cells",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("row_id", sa.Uuid(), sa.ForeignKey("literature_matrix_rows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field", sa.String(24), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("chunk_id", sa.String(64), sa.ForeignKey("evidence_chunks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("reader_version", sa.String(160), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.UniqueConstraint("row_id", "field", name="uq_matrix_row_field"),
        sa.CheckConstraint("field IN ('question','method','sample','finding','limitation')", name=op.f("ck_literature_matrix_cells_valid_field")),
    )


def downgrade() -> None:
    op.drop_table("literature_matrix_cells")
    op.drop_index("ix_matrix_project_created", table_name="literature_matrix_rows")
    op.drop_table("literature_matrix_rows")
