"""Immutable file snapshots for reference CSV and draft Markdown exports."""

import sqlalchemy as sa

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "export_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("research_projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("draft_id", sa.Uuid(), sa.ForeignKey("writing_drafts.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("filename", sa.String(100), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("body", sa.LargeBinary(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('reference_csv','draft_markdown')", name=op.f("ck_export_records_valid_kind")),
        sa.CheckConstraint("byte_size > 0 AND byte_size <= 2097152", name=op.f("ck_export_records_bounded_size")),
        sa.UniqueConstraint("project_id", "request_id", name="uq_export_project_request"),
    )
    op.create_index("ix_export_project_created", "export_records", ["project_id", "created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_export_project_created", table_name="export_records")
    op.drop_table("export_records")
