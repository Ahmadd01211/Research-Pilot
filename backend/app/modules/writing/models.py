from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class WritingDraft(Base):
    __tablename__ = "writing_drafts"
    __table_args__ = (
        CheckConstraint("revision >= 1", name="positive_revision"),
        Index("ix_writing_project_updated", "project_id", "updated_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("research_projects.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(180))
    body: Mapped[str] = mapped_column(Text)
    reference_ids: Mapped[list[str]] = mapped_column(JSONB)
    revision: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WritingVersion(Base):
    __tablename__ = "writing_versions"
    __table_args__ = (
        UniqueConstraint("draft_id", "revision", name="uq_writing_draft_revision"),
        CheckConstraint("revision >= 1", name="positive_revision"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    draft_id: Mapped[UUID] = mapped_column(ForeignKey("writing_drafts.id", ondelete="RESTRICT"))
    revision: Mapped[int] = mapped_column()
    title: Mapped[str] = mapped_column(String(180))
    body: Mapped[str] = mapped_column(Text)
    reference_ids: Mapped[list[str]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
