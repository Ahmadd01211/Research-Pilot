"""Persist cited Research Chat threads and immutable turn provenance."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_chat_threads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("research_projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(title) BETWEEN 1 AND 160", name="ck_research_chat_threads_valid_title"),
    )
    op.create_index(
        "ix_chat_thread_project_updated",
        "research_chat_threads",
        ["project_id", "updated_at", "id"],
    )
    op.create_table(
        "research_chat_turns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "thread_id",
            sa.Uuid(),
            sa.ForeignKey("research_chat_threads.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("turn_number >= 1", name="ck_research_chat_turns_positive_turn_number"),
        sa.UniqueConstraint("thread_id", "turn_number", name="uq_chat_turn_number"),
    )
    op.create_index("ix_chat_turn_thread", "research_chat_turns", ["thread_id", "turn_number"])


def downgrade() -> None:
    op.drop_index("ix_chat_turn_thread", table_name="research_chat_turns")
    op.drop_table("research_chat_turns")
    op.drop_index("ix_chat_thread_project_updated", table_name="research_chat_threads")
    op.drop_table("research_chat_threads")
