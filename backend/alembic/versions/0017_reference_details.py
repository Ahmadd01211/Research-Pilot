"""Store verified journal and publisher metadata without changing existing records."""
import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None
FIELDS = {"volume": 40, "issue": 40, "pages": 80, "article_number": 80,
          "publisher": 300, "edition": 80}


def upgrade() -> None:
    for name, size in FIELDS.items():
        op.add_column("reference_records", sa.Column(name, sa.String(size), nullable=False, server_default=""))


def downgrade() -> None:
    for name in reversed(FIELDS):
        op.drop_column("reference_records", name)
