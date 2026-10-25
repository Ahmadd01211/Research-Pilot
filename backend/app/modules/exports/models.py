from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class ExportRecord(Base):
    __tablename__ = "export_records"
    __table_args__ = (
        CheckConstraint("kind IN ('reference_csv','reference_xlsx','matrix_csv','matrix_xlsx','draft_markdown','draft_docx')", name="valid_kind"),
        CheckConstraint("byte_size > 0 AND byte_size <= 2097152", name="bounded_size"),
        UniqueConstraint("project_id", "request_id", name="uq_export_project_request"),
        Index("ix_export_project_created", "project_id", "created_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("research_projects.id", ondelete="RESTRICT"))
    draft_id: Mapped[UUID | None] = mapped_column(ForeignKey("writing_drafts.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String(32))
    filename: Mapped[str] = mapped_column(String(100))
    content_type: Mapped[str] = mapped_column(String(100))
    body: Mapped[bytes] = mapped_column(LargeBinary)
    sha256: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column()
    request_id: Mapped[UUID] = mapped_column()
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
