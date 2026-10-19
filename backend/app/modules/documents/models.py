from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("project_id", "sha256", name="uq_document_project_hash"),
        CheckConstraint("byte_size > 0 AND byte_size <= 20971520", name="bounded_size"),
        Index("ix_document_project_created", "project_id", "created_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_projects.id", ondelete="RESTRICT")
    )
    filename: Mapped[str] = mapped_column(String(180))
    sha256: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    processing: Mapped["DocumentJob | None"] = relationship(
        back_populates="document", uselist=False, lazy="selectin"
    )

    @property
    def status(self) -> str:
        return self.processing.state if self.processing else "stored"


class DocumentJob(Base):
    __tablename__ = "document_jobs"
    __table_args__ = (
        CheckConstraint(
            "state IN ('queued','processing','extracted','failed','cancelled')", name="valid_state"
        ),
        CheckConstraint("attempts >= 0 AND attempts <= 5", name="bounded_attempts"),
        Index("ix_job_dispatch", "state", "dispatch_after"),
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), primary_key=True
    )
    state: Mapped[str] = mapped_column(String(16), default="queued")
    attempts: Mapped[int] = mapped_column(default=0)
    lease_token: Mapped[UUID | None] = mapped_column()
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatch_after: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(40))
    page_count: Mapped[int | None] = mapped_column()
    extractor_version: Mapped[str | None] = mapped_column(String(80))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    document: Mapped[Document] = relationship(back_populates="processing")


class DocumentPageText(Base):
    __tablename__ = "document_pages"
    __table_args__ = (
        CheckConstraint("page_number >= 1 AND page_number <= 300", name="bounded_page"),
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), primary_key=True
    )
    page_number: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    layout: Mapped[dict[str, object] | None] = mapped_column(JSONB)


class ProcessingHeartbeat(Base):
    __tablename__ = "processing_heartbeat"
    id: Mapped[int] = mapped_column(primary_key=True)
    ticked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EvidenceChunk(Base):
    __tablename__ = "evidence_chunks"
    __table_args__ = (
        CheckConstraint("kind IN ('prose','table_row','figure_caption')", name="valid_kind"),
        CheckConstraint("page_number >= 1 AND page_number <= 300", name="bounded_page"),
        Index("ix_chunk_document_reader", "document_id", "reader_version", "page_number"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="RESTRICT"))
    source_sha256: Mapped[str] = mapped_column(String(64))
    reader_version: Mapped[str] = mapped_column(String(160))
    chunker_version: Mapped[str] = mapped_column(String(40))
    page_number: Mapped[int] = mapped_column()
    kind: Mapped[str] = mapped_column(String(24))
    source_id: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)
    source_metadata: Mapped[dict[str, object]] = mapped_column(JSONB)
