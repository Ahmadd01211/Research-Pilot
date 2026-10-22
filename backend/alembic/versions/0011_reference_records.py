"""Manual reference records and a project citation-style preference."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reference_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("research_projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("title_key", sa.String(500), nullable=False),
        sa.Column("authors", JSONB(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("container_title", sa.String(500), nullable=False),
        sa.Column("doi", sa.String(260), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("revision >= 1", name=op.f("ck_reference_records_positive_revision")),
        sa.CheckConstraint("year IS NULL OR (year >= 1500 AND year <= 2100)", name=op.f("ck_reference_records_bounded_year")),
        sa.CheckConstraint("kind IN ('journal','book','conference','preprint','other')", name=op.f("ck_reference_records_valid_kind")),
    )
    op.create_index("ix_reference_project_created", "reference_records", ["project_id", "created_at", "id"])
    op.create_index("uq_active_project_doi", "reference_records", ["project_id", "doi"],
                    unique=True, postgresql_where=sa.text("deleted_at IS NULL AND doi IS NOT NULL"))
    op.create_table(
        "reference_settings",
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("research_projects.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("style", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("style IN ('apa7','mla9','chicago18')", name=op.f("ck_reference_settings_valid_style")),
        sa.CheckConstraint("revision >= 1", name=op.f("ck_reference_settings_positive_revision")),
    )


def downgrade() -> None:
    op.drop_table("reference_settings")
    op.drop_index("uq_active_project_doi", table_name="reference_records")
    op.drop_index("ix_reference_project_created", table_name="reference_records")
    op.drop_table("reference_records")
