"""Keep prior matrix cells when gap candidates cite them."""

import sqlalchemy as sa

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("literature_matrix_cells", sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint("uq_matrix_row_field", "literature_matrix_cells", type_="unique")
    op.create_index("uq_active_matrix_row_field", "literature_matrix_cells", ["row_id", "field"],
                    unique=True, postgresql_where=sa.text("superseded_at IS NULL"))


def downgrade() -> None:
    op.drop_index("uq_active_matrix_row_field", table_name="literature_matrix_cells")
    op.execute("DELETE FROM literature_matrix_cells WHERE superseded_at IS NOT NULL")
    op.create_unique_constraint("uq_matrix_row_field", "literature_matrix_cells", ["row_id", "field"])
    op.drop_column("literature_matrix_cells", "superseded_at")
