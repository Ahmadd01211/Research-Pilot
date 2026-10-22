from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class ReferenceRecord(Base):
    __tablename__ = "reference_records"
    __table_args__ = (
        CheckConstraint("revision >= 1", name="positive_revision"),
        CheckConstraint("year IS NULL OR (year >= 1500 AND year <= 2100)", name="bounded_year"),
        CheckConstraint(
            "kind IN ('journal','book','conference','preprint','other')", name="valid_kind"
        ),
        Index("ix_reference_project_created", "project_id", "created_at", "id"),
        Index("uq_active_project_doi", "project_id", "doi", unique=True,
              postgresql_where=text("deleted_at IS NULL AND doi IS NOT NULL")),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("research_projects.id", ondelete="RESTRICT"))
    document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(500))
    title_key: Mapped[str] = mapped_column(String(500))
    authors: Mapped[list[str]] = mapped_column(JSONB)
    year: Mapped[int | None] = mapped_column()
    container_title: Mapped[str] = mapped_column(String(500))
    doi: Mapped[str | None] = mapped_column(String(260))
    url: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReferenceSettings(Base):
    __tablename__ = "reference_settings"
    __table_args__ = (
        CheckConstraint("style IN ('apa7','mla9','chicago18')", name="valid_style"),
        CheckConstraint("revision >= 1", name="positive_revision"),
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_projects.id", ondelete="RESTRICT"), primary_key=True
    )
    style: Mapped[str] = mapped_column(String(16))
    revision: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
