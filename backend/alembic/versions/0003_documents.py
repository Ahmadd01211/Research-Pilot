"""Private immutable PDF uploads; parsing and version replacement follow separately."""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("research_projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(180), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "sha256", name="uq_document_project_hash"),
        sa.CheckConstraint(
            "byte_size > 0 AND byte_size <= 20971520", name=op.f("ck_documents_bounded_size")
        ),
    )
    op.create_index("ix_document_project_created", "documents", ["project_id", "created_at", "id"])


def downgrade() -> None:
    op.drop_table("documents")
