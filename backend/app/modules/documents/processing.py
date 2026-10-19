"""Durable job/outbox, bounded leases, and fenced atomic page publication."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import delete, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from app.modules.documents.chunks import make_chunks
from app.modules.documents.extraction import EXTRACTOR_VERSION, TRANSIENT, extract_with_layout
from app.modules.documents.models import Document, DocumentJob, DocumentPageText, EvidenceChunk
from app.modules.documents.storage import LocalStorage
from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.projects import service as projects
from app.modules.projects.models import ResearchProject

LEASE_SECONDS = 240  # Longer than Celery's hard task limit (150s).
AUTO_ATTEMPTS = 3
MAX_ATTEMPTS = 5


def locked_job(db: Session, document_id: UUID) -> DocumentJob | None:
    return db.scalar(
        select(DocumentJob)
        .where(DocumentJob.document_id == document_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def dispatch_once(factory: sessionmaker[Session], publish: Callable[[str], None]) -> int:
    """Job rows are the transactional outbox. Publish may repeat; claims are idempotent."""
    now = datetime.now(UTC)
    sent = 0
    with factory() as db:
        jobs = db.scalars(
            select(DocumentJob)
            .where(
                or_(
                    (DocumentJob.state == "queued") & (DocumentJob.dispatch_after <= now),
                    (DocumentJob.state == "processing") & (DocumentJob.lease_until <= now),
                )
            )
            .order_by(DocumentJob.dispatch_after)
            .limit(20)
            .with_for_update(skip_locked=True)
        ).all()
        for job in jobs:
            if job.state == "processing":
                job.lease_token = None
                job.lease_until = None
                job.error_code = "worker_failure"
                job.state = "queued" if job.attempts < AUTO_ATTEMPTS else "failed"
            if job.state != "queued":
                continue
            # If publishing fails, rollback preserves intent. If commit is ambiguous,
            # redelivery is safe. A queued row is republished until a worker claims it.
            publish(str(job.document_id))
            job.dispatch_after = now + timedelta(seconds=30)
            sent += 1
        db.commit()
    return sent


def claim(factory: sessionmaker[Session], document_id: UUID) -> tuple[UUID, str] | None:
    with factory() as db:
        document = db.get(Document, document_id)
        if document is None:
            return None
        project = db.scalar(
            select(ResearchProject)
            .where(ResearchProject.id == document.project_id)
            .with_for_update()
        )
        job = locked_job(db, document_id)
        if job is None or job.state != "queued":
            return None
        if project is None or project.deleted_at is not None:
            job.state = "cancelled"
            job.lease_token = None
            db.commit()
            return None
        if job.attempts >= MAX_ATTEMPTS:
            job.state = "failed"
            db.commit()
            return None
        token = uuid4()
        job.state = "processing"
        job.attempts += 1
        job.lease_token = token
        job.lease_until = datetime.now(UTC) + timedelta(seconds=LEASE_SECONDS)
        job.error_code = None
        db.commit()
        return token, document.sha256


def finish(
    factory: sessionmaker[Session],
    document_id: UUID,
    token: UUID,
    pages: list[str] | None,
    error: str | None,
    layouts: list[dict[str, object]] | None = None,
) -> bool:
    with factory() as db:
        document = db.get(Document, document_id)
        if document is None:
            return False
        project = db.scalar(
            select(ResearchProject)
            .where(ResearchProject.id == document.project_id)
            .with_for_update()
        )
        job = locked_job(db, document_id)
        if (
            job is None
            or job.state != "processing"
            or job.lease_token != token
            or job.lease_until is None
            or job.lease_until <= datetime.now(UTC)
        ):
            return False  # A stale worker cannot overwrite a newer attempt.
        job.lease_token = None
        job.lease_until = None
        if project is None or project.deleted_at is not None:
            job.state = "cancelled"
        elif error:
            job.error_code = error
            job.state = (
                "queued" if error in TRANSIENT and job.attempts < AUTO_ATTEMPTS else "failed"
            )
            job.dispatch_after = datetime.now(UTC) + timedelta(seconds=15)
        elif pages is not None:
            db.execute(delete(DocumentPageText).where(DocumentPageText.document_id == document_id))
            db.add_all(
                [
                    DocumentPageText(
                        document_id=document_id,
                        page_number=n,
                        text=text,
                        layout=layouts[n - 1] if layouts else None,
                    )
                    for n, text in enumerate(pages, 1)
                ]
            )
            if layouts:
                # Preserve prior derived versions; identical retries add nothing.
                for chunk in make_chunks(document_id, document.sha256, layouts):
                    db.execute(
                        insert(EvidenceChunk)
                        .values(**chunk)
                        .on_conflict_do_nothing(index_elements=[EvidenceChunk.id])
                    )
            job.page_count = len(pages)
            job.extractor_version = EXTRACTOR_VERSION
            job.completed_at = datetime.now(UTC)
            job.state = "extracted"
            projects.record(
                db, project, "paper_extracted", "PDF text extracted with page provenance", []
            )
        else:
            job.state = "failed"
            job.error_code = "worker_failure"
        db.commit()
        return True


def run_document(factory: sessionmaker[Session], storage: LocalStorage, document_id: UUID) -> None:
    claimed = claim(factory, document_id)
    if claimed is None:
        return
    token, source_hash = claimed
    pages, layouts, error = extract_with_layout(storage.path(document_id), source_hash)
    finish(factory, document_id, token, pages, error, layouts)


def retry(db: Session, owner: UUID, project_id: UUID, document_id: UUID) -> Document:
    project = projects.owned(db, owner, project_id, lock=True)
    document = db.scalar(
        select(Document).where(Document.id == document_id, Document.project_id == project_id)
    )
    if document is None:
        raise HTTPException(404, "Document not found")
    if project.archived_at:
        raise HTTPException(409, "Restore the project before retrying extraction")
    job = locked_job(db, document_id)
    if (
        job is None
        or job.state != "failed"
        or job.error_code not in TRANSIENT
        or job.attempts >= MAX_ATTEMPTS
    ):
        raise HTTPException(409, "This outcome cannot be retried; check its explanation")
    job.state = "queued"
    job.error_code = None
    job.dispatch_after = datetime.now(UTC)
    projects.record(db, project, "paper_retry", "PDF extraction retry requested", [])
    db.commit()
    db.refresh(document)
    return document
