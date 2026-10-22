from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base


class GapCandidate(Base):
    __tablename__ = "gap_candidates"
    __table_args__ = (
        CheckConstraint("revision >= 1", name="positive_revision"),
        Index("ix_gap_project_created", "project_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("research_projects.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(160))
    rationale: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence: Mapped[list["GapEvidence"]] = relationship(back_populates="gap", lazy="selectin")


class GapEvidence(Base):
    __tablename__ = "gap_evidence"
    __table_args__ = (
        UniqueConstraint("gap_id", "matrix_cell_id", name="uq_gap_cell"),
        CheckConstraint("stance IN ('supports','challenges')", name="valid_stance"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    gap_id: Mapped[UUID] = mapped_column(ForeignKey("gap_candidates.id", ondelete="CASCADE"))
    matrix_cell_id: Mapped[UUID] = mapped_column(ForeignKey("literature_matrix_cells.id", ondelete="RESTRICT"))
    stance: Mapped[str] = mapped_column(String(16))
    gap: Mapped[GapCandidate] = relationship(back_populates="evidence")
