"""Researcher writing drafts with immutable saved versions."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "writing_drafts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("research_projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("reference_ids", JSONB(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("revision >= 1", name=op.f("ck_writing_drafts_positive_revision")),
    )
    op.create_index("ix_writing_project_updated", "writing_drafts", ["project_id", "updated_at", "id"])
    op.create_table(
        "writing_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("draft_id", sa.Uuid(), sa.ForeignKey("writing_drafts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("reference_ids", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("draft_id", "revision", name="uq_writing_draft_revision"),
        sa.CheckConstraint("revision >= 1", name=op.f("ck_writing_versions_positive_revision")),
    )


def downgrade() -> None:
    op.drop_table("writing_versions")
    op.drop_index("ix_writing_project_updated", table_name="writing_drafts")
    op.drop_table("writing_drafts")
