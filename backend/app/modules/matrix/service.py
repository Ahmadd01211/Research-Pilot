"""Matrix authoring and source checks stay on the server."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.documents.chunks import CHUNKER_VERSION
from app.modules.documents.models import Document, EvidenceChunk
from app.modules.documents.reader import READER_VERSION
from app.modules.documents.service import owned as owned_document
from app.modules.matrix.models import MatrixCell, MatrixRow
from app.modules.matrix.schemas import (
    CellInput,
    CellRead,
    MatrixRead,
    RowCreate,
    RowDelete,
    RowRead,
    RowUpdate,
    SourcePage,
    SourceRead,
)
from app.modules.projects.service import owned as owned_project

MAX_ROWS = 200


def _editable(db: Session, owner: UUID, project_id: UUID) -> None:
    project = owned_project(db, owner, project_id, lock=True)
    if project.archived_at is not None:
        raise HTTPException(409, "Restore the project before editing its matrix")


def _row(db: Session, owner: UUID, project_id: UUID, row_id: UUID, *, lock: bool = False) -> MatrixRow:
    owned_project(db, owner, project_id)
    statement = select(MatrixRow).where(
        MatrixRow.id == row_id, MatrixRow.project_id == project_id,
        MatrixRow.deleted_at.is_(None),
    )
    row = db.scalar(statement.with_for_update() if lock else statement)
    if row is None:
        raise HTTPException(404, "Matrix row not found")
    return row


def _read(db: Session, row: MatrixRow) -> RowRead:
    document = db.get(Document, row.document_id)
    assert document is not None
    cells = []
    for cell in sorted((item for item in row.cells if item.superseded_at is None),
                       key=lambda item: item.field):
        chunk = db.get(EvidenceChunk, cell.chunk_id)
        assert chunk is not None
        cells.append(CellRead(
            id=cell.id, field=cell.field, value=cell.value, chunk_id=cell.chunk_id,
            source_sha256=cell.source_sha256, reader_version=cell.reader_version,
            page_number=cell.page_number, kind=chunk.kind,
            source_metadata=chunk.source_metadata,
        ))
    return RowRead(
        id=row.id, document_id=row.document_id, document_filename=document.filename,
        revision=row.revision, created_at=row.created_at, updated_at=row.updated_at, cells=cells,
    )


def list_rows(db: Session, owner: UUID, project_id: UUID) -> MatrixRead:
    owned_project(db, owner, project_id)
    rows = db.scalars(select(MatrixRow).where(
        MatrixRow.project_id == project_id, MatrixRow.deleted_at.is_(None),
    ).order_by(MatrixRow.created_at, MatrixRow.id).limit(MAX_ROWS)).all()
    return MatrixRead(items=[_read(db, row) for row in rows])


def list_sources(db: Session, owner: UUID, project_id: UUID, document_id: UUID,
                 page: int | None, offset: int, limit: int) -> SourcePage:
    document = owned_document(db, owner, project_id, document_id)
    where = (
        EvidenceChunk.document_id == document_id,
        EvidenceChunk.source_sha256 == document.sha256,
        EvidenceChunk.reader_version == READER_VERSION,
        EvidenceChunk.chunker_version == CHUNKER_VERSION,
    )
    filters = (*where, EvidenceChunk.page_number == page) if page is not None else where
    total = db.scalar(select(func.count()).select_from(EvidenceChunk).where(*filters)) or 0
    chunks = db.scalars(select(EvidenceChunk).where(*filters).order_by(
        EvidenceChunk.page_number, EvidenceChunk.kind, EvidenceChunk.id,
    ).offset(offset).limit(limit)).all()
    return SourcePage(items=[SourceRead(
        chunk_id=item.id, page_number=item.page_number, kind=item.kind,
        text=item.text, source_sha256=item.source_sha256,
        reader_version=item.reader_version, source_metadata=item.source_metadata,
    ) for item in chunks], total=total)


def _cells(db: Session, document: Document, inputs: list[CellInput], row_id: UUID) -> list[MatrixCell]:
    if len({cell.field for cell in inputs}) != len(inputs):
        raise HTTPException(422, "Use each matrix field once")
    chunks = {item.id: item for item in db.scalars(select(EvidenceChunk).where(
        EvidenceChunk.id.in_([cell.chunk_id for cell in inputs]),
        EvidenceChunk.document_id == document.id,
        EvidenceChunk.source_sha256 == document.sha256,
        EvidenceChunk.reader_version == READER_VERSION,
        EvidenceChunk.chunker_version == CHUNKER_VERSION,
    )).all()}
    if len(chunks) != len({cell.chunk_id for cell in inputs}):
        raise HTTPException(422, "Choose a current source passage from this paper for every field")
    return [MatrixCell(
        row_id=row_id, field=cell.field, value=cell.value.strip(), chunk_id=cell.chunk_id,
        source_sha256=chunks[cell.chunk_id].source_sha256,
        reader_version=chunks[cell.chunk_id].reader_version,
        page_number=chunks[cell.chunk_id].page_number,
        superseded_at=None,
    ) for cell in inputs]


def create(db: Session, owner: UUID, project_id: UUID, data: RowCreate) -> RowRead:
    _editable(db, owner, project_id)
    document = owned_document(db, owner, project_id, data.document_id)
    total = db.scalar(select(func.count()).select_from(MatrixRow).where(
        MatrixRow.project_id == project_id, MatrixRow.deleted_at.is_(None),
    )) or 0
    if total >= MAX_ROWS:
        raise HTTPException(409, "Matrix row limit reached")
    now = datetime.now(UTC)
    row = MatrixRow(project_id=project_id, document_id=document.id, revision=1,
                    created_at=now, updated_at=now, deleted_at=None)
    db.add(row)
    db.flush()
    db.add_all(_cells(db, document, data.cells, row.id))
    db.commit()
    db.expire_all()
    return _read(db, row)


def update(db: Session, owner: UUID, project_id: UUID, row_id: UUID, data: RowUpdate) -> RowRead:
    _editable(db, owner, project_id)
    row = _row(db, owner, project_id, row_id, lock=True)
    if row.revision != data.expected_revision:
        raise HTTPException(409, "This matrix row changed. Review the latest version before saving")
    document = owned_document(db, owner, project_id, row.document_id)
    cells = _cells(db, document, data.cells, row.id)
    now = datetime.now(UTC)
    for old_cell in row.cells:
        if old_cell.superseded_at is None:
            old_cell.superseded_at = now
    db.flush()
    db.add_all(cells)
    row.revision += 1
    row.updated_at = now
    db.commit()
    db.expire_all()
    return _read(db, row)


def remove(db: Session, owner: UUID, project_id: UUID, row_id: UUID, data: RowDelete) -> None:
    _editable(db, owner, project_id)
    row = _row(db, owner, project_id, row_id, lock=True)
    if row.revision != data.expected_revision:
        raise HTTPException(409, "This matrix row changed. Review the latest version before removing")
    row.deleted_at = datetime.now(UTC)
    row.revision += 1
    row.updated_at = row.deleted_at
    db.commit()
