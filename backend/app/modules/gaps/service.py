"""Candidate gaps are bounded hypotheses with inspectable matrix provenance."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.modules.documents.chunks import CHUNKER_VERSION
from app.modules.documents.models import Document, EvidenceChunk
from app.modules.documents.reader import READER_VERSION
from app.modules.gaps.models import GapCandidate, GapEvidence
from app.modules.gaps.schemas import (
    EvidenceInput,
    EvidenceRead,
    GapCreate,
    GapPage,
    GapRead,
    GapRemove,
    GapUpdate,
    Uncertainty,
)
from app.modules.matrix.models import MatrixCell, MatrixRow
from app.modules.projects.service import owned as owned_project

MAX_GAPS = 100


def _editable(db: Session, owner: UUID, project_id: UUID) -> None:
    project = owned_project(db, owner, project_id, lock=True)
    if project.archived_at is not None:
        raise HTTPException(409, "Restore the project before editing gap candidates")


def _gap(db: Session, owner: UUID, project_id: UUID, gap_id: UUID,
         *, lock: bool = False) -> GapCandidate:
    owned_project(db, owner, project_id)
    statement = select(GapCandidate).where(
        GapCandidate.id == gap_id, GapCandidate.project_id == project_id,
        GapCandidate.deleted_at.is_(None),
    )
    gap = db.scalar(statement.with_for_update() if lock else statement)
    if gap is None:
        raise HTTPException(404, "Gap candidate not found")
    return gap


def _read(db: Session, gap: GapCandidate) -> GapRead:
    evidence = []
    for link in gap.evidence:
        cell = db.get(MatrixCell, link.matrix_cell_id)
        assert cell is not None
        row = db.get(MatrixRow, cell.row_id)
        assert row is not None
        document = db.get(Document, row.document_id)
        chunk = db.get(EvidenceChunk, cell.chunk_id)
        assert document is not None and chunk is not None
        evidence.append(EvidenceRead(
            matrix_cell_id=cell.id, stance=link.stance, field=cell.field, value=cell.value,
            document_id=document.id, document_filename=document.filename,
            page_number=cell.page_number, source_sha256=cell.source_sha256,
            reader_version=cell.reader_version, kind=chunk.kind,
            source_metadata=chunk.source_metadata,
            stale=bool(row.deleted_at or cell.superseded_at or cell.source_sha256 != document.sha256
                       or cell.reader_version != READER_VERSION
                       or chunk.chunker_version != CHUNKER_VERSION),
        ))
    evidence.sort(key=lambda item: (item.stance != "supports", item.document_filename, item.field))
    supporting = {item.document_id for item in evidence if item.stance == "supports"}
    uncertainty: Uncertainty = "candidate_across_papers"
    if any(item.stale for item in evidence):
        uncertainty = "source_needs_review"
    elif any(item.stance == "challenges" for item in evidence):
        uncertainty = "mixed_evidence"
    elif len(supporting) < 2:
        uncertainty = "limited_coverage"
    return GapRead(
        id=gap.id, title=gap.title, rationale=gap.rationale, revision=gap.revision,
        created_at=gap.created_at, updated_at=gap.updated_at,
        uncertainty=uncertainty, supporting_papers=len(supporting), evidence=evidence,
    )


def list_gaps(db: Session, owner: UUID, project_id: UUID) -> GapPage:
    owned_project(db, owner, project_id)
    gaps = db.scalars(select(GapCandidate).where(
        GapCandidate.project_id == project_id, GapCandidate.deleted_at.is_(None),
    ).order_by(GapCandidate.created_at.desc(), GapCandidate.id.desc()).limit(MAX_GAPS)).all()
    return GapPage(items=[_read(db, gap) for gap in gaps])


def _links(db: Session, project_id: UUID, gap_id: UUID,
           inputs: list[EvidenceInput]) -> list[GapEvidence]:
    if len({item.matrix_cell_id for item in inputs}) != len(inputs):
        raise HTTPException(422, "Use each matrix field once per gap candidate")
    if not any(item.stance == "supports" for item in inputs):
        raise HTTPException(422, "Add at least one supporting matrix field")
    links = []
    for item in inputs:
        cell = db.get(MatrixCell, item.matrix_cell_id)
        row = db.get(MatrixRow, cell.row_id) if cell else None
        document = db.get(Document, row.document_id) if row else None
        chunk = db.get(EvidenceChunk, cell.chunk_id) if cell else None
        if (cell is None or row is None or document is None
            or chunk is None
            or row.project_id != project_id or row.deleted_at is not None
            or cell.superseded_at is not None
            or document.project_id != project_id or cell.source_sha256 != document.sha256
            or cell.reader_version != READER_VERSION
            or chunk.chunker_version != CHUNKER_VERSION):
            raise HTTPException(422, "Choose active, current matrix fields from this project")
        links.append(GapEvidence(gap_id=gap_id, matrix_cell_id=cell.id, stance=item.stance))
    return links


def create(db: Session, owner: UUID, project_id: UUID, data: GapCreate) -> GapRead:
    _editable(db, owner, project_id)
    total = db.scalar(select(func.count()).select_from(GapCandidate).where(
        GapCandidate.project_id == project_id, GapCandidate.deleted_at.is_(None),
    )) or 0
    if total >= MAX_GAPS:
        raise HTTPException(409, "Gap candidate limit reached")
    now = datetime.now(UTC)
    gap = GapCandidate(project_id=project_id, title=data.title, rationale=data.rationale,
                       revision=1, created_at=now, updated_at=now, deleted_at=None)
    db.add(gap)
    db.flush()
    db.add_all(_links(db, project_id, gap.id, data.evidence))
    db.commit()
    db.expire_all()
    return _read(db, gap)


def update(db: Session, owner: UUID, project_id: UUID, gap_id: UUID,
           data: GapUpdate) -> GapRead:
    _editable(db, owner, project_id)
    gap = _gap(db, owner, project_id, gap_id, lock=True)
    if gap.revision != data.expected_revision:
        raise HTTPException(409, "This candidate changed. Review the latest version before saving")
    links = _links(db, project_id, gap.id, data.evidence)
    db.execute(delete(GapEvidence).where(GapEvidence.gap_id == gap.id))
    db.add_all(links)
    gap.title = data.title
    gap.rationale = data.rationale
    gap.revision += 1
    gap.updated_at = datetime.now(UTC)
    db.commit()
    db.expire_all()
    return _read(db, gap)


def remove(db: Session, owner: UUID, project_id: UUID, gap_id: UUID,
           data: GapRemove) -> None:
    _editable(db, owner, project_id)
    gap = _gap(db, owner, project_id, gap_id, lock=True)
    if gap.revision != data.expected_revision:
        raise HTTPException(409, "This candidate changed. Review the latest version before removing")
    gap.deleted_at = datetime.now(UTC)
    gap.updated_at = gap.deleted_at
    gap.revision += 1
    db.commit()
