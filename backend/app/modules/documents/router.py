import hashlib
import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.dependencies import current_user, database, settings_for
from app.modules.documents import processing, service
from app.modules.documents.models import DocumentPageText
from app.modules.documents.schemas import DocumentPage, DocumentRead, EvidencePage, UploadResult
from app.modules.documents.storage import LocalStorage
from app.modules.identity.models import User
from app.modules.projects.service import owned

router = APIRouter(prefix="/api/v1/projects/{project_id}/documents", tags=["documents"])


@router.get("", response_model=DocumentPage)
def documents(
    project_id: UUID,
    offset: int = Query(0, ge=0, le=100),
    limit: int = Query(25, ge=1, le=50),
    user: User = Depends(current_user),
    db: Session = Depends(database),
) -> DocumentPage:
    return service.list_documents(db, user.id, project_id, offset, limit)


@router.post(
    "",
    response_model=UploadResult,
    status_code=200,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
async def upload(
    request: Request,
    project_id: UUID,
    filename: str = Query(min_length=5, max_length=180),
    user: User = Depends(current_user),
    db: Session = Depends(database),
    settings: Settings = Depends(settings_for),
) -> UploadResult:
    # Raw streaming avoids multipart spooling before authentication. Filename is display metadata only.
    if request.headers.get("content-type", "").split(";")[0].lower() != "application/pdf":
        raise HTTPException(415, "Upload a PDF file")
    if not filename.lower().endswith(".pdf") or any(ord(c) < 32 or c in "/\\" for c in filename):
        raise HTTPException(422, "Use a PDF filename without path separators or control characters")
    project = await run_in_threadpool(owned, db, user.id, project_id)
    if project.archived_at:
        raise HTTPException(409, "Restore the project before uploading papers")
    # Release the read transaction during potentially slow network I/O.
    owner_id = user.id
    db.rollback()
    storage = LocalStorage(settings.storage_root)
    staged = storage.stage()
    size = 0
    digest = hashlib.sha256()
    header = b""
    try:
        with staged.open("xb") as output:
            async for chunk in request.stream():
                size += len(chunk)
                if size > service.MAX_BYTES:
                    raise HTTPException(413, "PDF must be no larger than 20 MiB")
                header = (header + chunk)[:5]
                digest.update(chunk)
                output.write(chunk)
            if header != b"%PDF-":
                raise HTTPException(422, "The file does not have a PDF signature")
            output.flush()
            os.fsync(output.fileno())
        return await run_in_threadpool(
            service.store,
            db,
            owner_id,
            project_id,
            filename.strip(),
            staged,
            digest.hexdigest(),
            size,
            storage,
        )
    finally:
        staged.unlink(missing_ok=True)


@router.get("/{document_id}", response_model=DocumentRead)
def document(
    project_id: UUID,
    document_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(database),
) -> DocumentRead:
    return DocumentRead.model_validate(service.owned(db, user.id, project_id, document_id))


@router.get("/{document_id}/download", response_class=FileResponse)
def download(
    project_id: UUID,
    document_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(database),
    settings: Settings = Depends(settings_for),
) -> FileResponse:
    paper = service.owned(db, user.id, project_id, document_id)
    path = LocalStorage(settings.storage_root).path(paper.id)
    if not path.is_file():
        raise HTTPException(503, "Stored file is temporarily unavailable")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=paper.filename,
        content_disposition_type="attachment",
    )


@router.post("/{document_id}/retry", response_model=DocumentRead)
def retry_extraction(
    project_id: UUID,
    document_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(database),
) -> DocumentRead:
    return DocumentRead.model_validate(processing.retry(db, user.id, project_id, document_id))


@router.get("/{document_id}/pages/{page_number}", response_model=EvidencePage)
def evidence_page(
    project_id: UUID,
    document_id: UUID,
    page_number: int,
    user: User = Depends(current_user),
    db: Session = Depends(database),
) -> EvidencePage:
    paper = service.owned(db, user.id, project_id, document_id)
    if paper.processing is None or paper.status != "extracted":
        raise HTTPException(409, "Text extraction has not completed")
    page = db.get(DocumentPageText, (document_id, page_number)) if 1 <= page_number <= 300 else None
    if page is None:
        raise HTTPException(404, "Page not found")
    return EvidencePage(
        document_id=document_id,
        page_number=page_number,
        text=page.text,
        layout=page.layout,
        source_sha256=paper.sha256,
        extractor_version=paper.processing.extractor_version or "unknown",
    )


@router.post("/{document_id}/prepare-reader", response_model=DocumentRead)
def prepare_reader(
    project_id: UUID,
    document_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(database),
) -> DocumentRead:
    project = owned(db, user.id, project_id, lock=True)
    paper = service.owned(db, user.id, project_id, document_id)
    if project.archived_at:
        raise HTTPException(409, "Restore the project before preparing its reader")
    job = processing.locked_job(db, document_id)
    first = db.get(DocumentPageText, (document_id, 1))
    if job is None or job.state != "extracted" or (first is not None and first.layout is not None):
        raise HTTPException(409, "Reader preparation is not needed or is already running")
    job.state = "queued"
    job.attempts = 0
    job.error_code = None
    from datetime import UTC, datetime

    job.dispatch_after = datetime.now(UTC)
    db.commit()
    db.refresh(paper)
    return DocumentRead.model_validate(paper)
