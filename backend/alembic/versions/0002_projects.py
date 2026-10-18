"""Add owner-scoped projects and transactional project activity."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("research_questions", postgresql.JSONB(), nullable=False),
        sa.Column("objectives", postgresql.JSONB(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("create_request_id", sa.Uuid(), nullable=False),
        sa.Column("create_payload_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("owner_id", "create_request_id", name="uq_project_owner_request"),
        sa.CheckConstraint("revision >= 1", name=op.f("ck_research_projects_positive_revision")),
    )
    op.create_index(
        "ix_project_owner_created", "research_projects", ["owner_id", "created_at", "id"]
    )
    op.create_table(
        "project_activities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("research_projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("summary", sa.String(160), nullable=False),
        sa.Column("changed_fields", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_activity_project_created", "project_activities", ["project_id", "created_at", "id"]
    )


def downgrade() -> None:
    op.drop_table("project_activities")
    op.drop_table("research_projects")
