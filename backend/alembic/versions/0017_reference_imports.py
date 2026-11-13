"""Idempotency records for reviewed BibTeX/RIS reference imports."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reference_imports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("research_projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("reference_ids", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "request_id", name="uq_reference_import_request"),
    )


def downgrade() -> None:
    op.drop_table("reference_imports")
