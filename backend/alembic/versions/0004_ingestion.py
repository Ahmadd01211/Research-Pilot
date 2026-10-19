"""Durable processing intent and page-linked extracted text."""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processing_heartbeat",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticked_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "document_jobs",
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_token", sa.Uuid()),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("dispatch_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_code", sa.String(40)),
        sa.Column("page_count", sa.Integer()),
        sa.Column("extractor_version", sa.String(80)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "state IN ('queued','processing','extracted','failed','cancelled')",
            name=op.f("ck_document_jobs_valid_state"),
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND attempts <= 5", name=op.f("ck_document_jobs_bounded_attempts")
        ),
    )
    op.create_index("ix_job_dispatch", "document_jobs", ["state", "dispatch_after"])
    op.create_table(
        "document_pages",
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("page_number", sa.Integer(), primary_key=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "page_number >= 1 AND page_number <= 300", name=op.f("ck_document_pages_bounded_page")
        ),
    )
    # Existing retained originals become real queued jobs; removed projects are cancelled.
    op.execute("""INSERT INTO document_jobs (document_id,state,attempts,dispatch_after)
        SELECT d.id, CASE WHEN p.deleted_at IS NULL THEN 'queued' ELSE 'cancelled' END, 0, CURRENT_TIMESTAMP
        FROM documents d JOIN research_projects p ON p.id=d.project_id""")


def downgrade() -> None:
    op.drop_table("document_pages")
    op.drop_table("document_jobs")
    op.drop_table("processing_heartbeat")
