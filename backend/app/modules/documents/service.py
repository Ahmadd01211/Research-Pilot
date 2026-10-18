from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.documents.models import Document
from app.modules.documents.schemas import DocumentPage, DocumentRead, UploadResult
from app.modules.documents.storage import LocalStorage
from app.modules.projects import service as projects

MAX_BYTES = 20 * 1024 * 1024
MAX_PROJECT_BYTES = 200 * 1024 * 1024
MAX_PROJECT_DOCUMENTS = 100


def list_documents(
    db: Session, owner: UUID, project_id: UUID, offset: int, limit: int
) -> DocumentPage:
    projects.owned(db, owner, project_id)
    where = Document.project_id == project_id
    total = db.scalar(select(func.count()).select_from(Document).where(where)) or 0
    rows = db.scalars(
        select(Document)
        .where(where)
        .order_by(Document.created_at.desc(), Document.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return DocumentPage(items=[DocumentRead.model_validate(row) for row in rows], total=total)


def owned(db: Session, owner: UUID, project_id: UUID, document_id: UUID) -> Document:
    projects.owned(db, owner, project_id)
    document = db.scalar(
        select(Document).where(Document.id == document_id, Document.project_id == project_id)
    )
    if document is None:
        raise HTTPException(404, "Document not found")
    return document


def store(
    db: Session,
    owner: UUID,
    project_id: UUID,
    filename: str,
    staged: Path,
    sha256: str,
    size: int,
    storage: LocalStorage,
) -> UploadResult:
    try:
        # Serialize with archive/delete and other uploads. No lock while receiving bytes.
        project = projects.owned(db, owner, project_id, lock=True)
        if project.archived_at:
            raise HTTPException(409, "Restore the project before uploading papers")
        prior = db.scalar(
            select(Document).where(Document.project_id == project_id, Document.sha256 == sha256)
        )
        if prior:
            return UploadResult(document=DocumentRead.model_validate(prior), duplicate=True)
        count, used = db.execute(
            select(func.count(), func.coalesce(func.sum(Document.byte_size), 0)).where(
                Document.project_id == project_id
            )
        ).one()
        if count >= MAX_PROJECT_DOCUMENTS or used + size > MAX_PROJECT_BYTES:
            raise HTTPException(409, "Project storage limit reached (100 papers or 200 MiB)")
        document = Document(
            id=uuid4(),
            project_id=project_id,
            filename=filename,
            sha256=sha256,
            byte_size=size,
            created_at=datetime.now(UTC),
        )
        storage.publish(staged, document.id)
        db.add(document)
        projects.record(db, project, "paper_stored", "PDF stored in project library", [])
        db.commit()
        return UploadResult(document=DocumentRead.model_validate(document), duplicate=False)
    except Exception:
        db.rollback()
        raise
    finally:
        staged.unlink(missing_ok=True)
        # A failed COMMIT can have an unknown outcome. Retain published bytes for
        # reconciliation rather than risk deleting an original whose row committed.
