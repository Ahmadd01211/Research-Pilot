from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class ResearchProject(Base):
    __tablename__ = "research_projects"
    __table_args__ = (
        UniqueConstraint("owner_id", "create_request_id", name="uq_project_owner_request"),
        CheckConstraint("revision >= 1", name="positive_revision"),
        Index("ix_project_owner_created", "owner_id", "created_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    research_questions: Mapped[list[str]] = mapped_column(JSONB)
    objectives: Mapped[list[str]] = mapped_column(JSONB)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    create_request_id: Mapped[UUID] = mapped_column()
    create_payload_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectActivity(Base):
    __tablename__ = "project_activities"
    __table_args__ = (Index("ix_activity_project_created", "project_id", "created_at", "id"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_projects.id", ondelete="RESTRICT")
    )
    action: Mapped[str] = mapped_column(String(24))
    summary: Mapped[str] = mapped_column(String(160))
    changed_fields: Mapped[list[str]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
