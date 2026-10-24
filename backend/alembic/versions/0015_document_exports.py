"""Allow immutable DOCX drafts and XLSX reference snapshots."""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_export_records_valid_kind"), "export_records", type_="check")
    op.create_check_constraint(
        op.f("ck_export_records_valid_kind"), "export_records",
        "kind IN ('reference_csv','reference_xlsx','draft_markdown','draft_docx')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_export_records_valid_kind"), "export_records", type_="check")
    op.create_check_constraint(
        op.f("ck_export_records_valid_kind"), "export_records",
        "kind IN ('reference_csv','draft_markdown')",
    )
