"""Researcher-authored candidate gaps with supporting and challenging matrix cells."""

import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gap_candidates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("research_projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("revision >= 1", name=op.f("ck_gap_candidates_positive_revision")),
    )
    op.create_index("ix_gap_project_created", "gap_candidates", ["project_id", "created_at", "id"])
    op.create_table(
        "gap_evidence",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("gap_id", sa.Uuid(), sa.ForeignKey("gap_candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("matrix_cell_id", sa.Uuid(), sa.ForeignKey("literature_matrix_cells.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("stance", sa.String(16), nullable=False),
        sa.UniqueConstraint("gap_id", "matrix_cell_id", name="uq_gap_cell"),
        sa.CheckConstraint("stance IN ('supports','challenges')", name=op.f("ck_gap_evidence_valid_stance")),
    )


def downgrade() -> None:
    op.drop_table("gap_evidence")
    op.drop_index("ix_gap_project_created", table_name="gap_candidates")
    op.drop_table("gap_candidates")
