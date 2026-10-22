from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base


class MatrixRow(Base):
    __tablename__ = "literature_matrix_rows"
    __table_args__ = (
        CheckConstraint("revision >= 1", name="positive_revision"),
        Index("ix_matrix_project_created", "project_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("research_projects.id", ondelete="RESTRICT"))
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="RESTRICT"))
    revision: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cells: Mapped[list["MatrixCell"]] = relationship(back_populates="row", lazy="selectin")


class MatrixCell(Base):
    __tablename__ = "literature_matrix_cells"
    __table_args__ = (
        Index("uq_active_matrix_row_field", "row_id", "field", unique=True,
              postgresql_where=text("superseded_at IS NULL")),
        CheckConstraint(
            "field IN ('question','method','sample','finding','limitation')", name="valid_field"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    row_id: Mapped[UUID] = mapped_column(ForeignKey("literature_matrix_rows.id", ondelete="CASCADE"))
    field: Mapped[str] = mapped_column(String(24))
    value: Mapped[str] = mapped_column(Text)
    chunk_id: Mapped[str] = mapped_column(String(64), ForeignKey("evidence_chunks.id", ondelete="RESTRICT"))
    source_sha256: Mapped[str] = mapped_column(String(64))
    reader_version: Mapped[str] = mapped_column(String(160))
    page_number: Mapped[int] = mapped_column()
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    row: Mapped[MatrixRow] = relationship(back_populates="cells")
