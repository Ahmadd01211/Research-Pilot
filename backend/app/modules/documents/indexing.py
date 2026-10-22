"""Durable, bounded embedding batches with versioned index publication."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.modules.documents.chunks import CHUNKER_VERSION
from app.modules.documents.embeddings import (
    DIMENSIONS,
    FORMAT_VERSION,
    MODEL,
    EmbeddingFailure,
    GoogleEmbeddings,
    vector_literal,
)
from app.modules.documents.models import (
    ChunkEmbedding,
    Document,
    DocumentIndex,
    DocumentPageText,
    EvidenceChunk,
)
from app.modules.documents.reader import READER_VERSION
from app.modules.documents.service import owned as owned_document
from app.modules.projects.models import ResearchProject
from app.modules.projects.service import owned as owned_project

MAX_BATCH = 8
MAX_FAILURES = 5
LEASE_SECONDS = 90


def current_index(db: Session, document: Document) -> DocumentIndex | None:
    return db.scalar(
        select(DocumentIndex).where(
            DocumentIndex.document_id == document.id,
            DocumentIndex.source_sha256 == document.sha256,
            DocumentIndex.reader_version == READER_VERSION,
            DocumentIndex.chunker_version == CHUNKER_VERSION,
            DocumentIndex.provider == "google",
            DocumentIndex.model == MODEL,
            DocumentIndex.dimensions == DIMENSIONS,
            DocumentIndex.format_version == FORMAT_VERSION,
        )
    )


def queue_index(
    db: Session, owner: UUID, project_id: UUID, document_id: UUID, settings: Settings
) -> DocumentIndex | None:
    if not settings.embedding_enabled or settings.google_api_key is None:
        raise HTTPException(503, "Research search is not configured")
    project = owned_project(db, owner, project_id, lock=True)
    document = owned_document(db, owner, project_id, document_id)
    if project.archived_at:
        raise HTTPException(409, "Restore the project before indexing its papers")
    if document.status != "extracted":
        raise HTTPException(409, "Extract the document before indexing")
    first = db.get(DocumentPageText, (document.id, 1))
    if first is None or not first.layout or first.layout.get("version") != READER_VERSION:
        # Old extracted papers need the current reader/chunker before their evidence
        # can be embedded. Reuse the durable extraction outbox; successful refresh
        # will queue the index in the same transaction that publishes its chunks.
        job = document.processing
        if job is None or job.state != "extracted":
            raise HTTPException(409, "Readable text cannot be refreshed right now")
        job.state = "queued"
        job.attempts = 0
        job.error_code = None
        job.dispatch_after = datetime.now(UTC)
        db.commit()
        return None
    existing = current_index(db, document)
    if existing is not None:
        return existing
    total = db.scalar(
        select(func.count()).select_from(EvidenceChunk).where(
            EvidenceChunk.document_id == document.id,
            EvidenceChunk.source_sha256 == document.sha256,
            EvidenceChunk.reader_version == READER_VERSION,
            EvidenceChunk.chunker_version == CHUNKER_VERSION,
        )
    ) or 0
    if not total:
        raise HTTPException(409, "No checked research evidence is available to index")
    now = datetime.now(UTC)
    index = DocumentIndex(
        id=uuid4(), document_id=document.id, source_sha256=document.sha256,
        reader_version=READER_VERSION, chunker_version=CHUNKER_VERSION,
        provider="google", model=MODEL, dimensions=DIMENSIONS, format_version=FORMAT_VERSION,
        state="queued", attempts=0, lease_token=None, lease_until=None,
        dispatch_after=now, error_code=None, processed_chunks=0, total_chunks=total,
        created_at=now, completed_at=None,
    )
    db.add(index)
    db.commit()
    return index


def queue_after_extraction(db: Session, document: Document, settings: Settings) -> DocumentIndex | None:
    """Create an index in the extraction transaction when embeddings are enabled.

    Returns None when indexing is disabled or the extracted source has no current,
    embeddable evidence chunks. The extraction itself remains successful either way.
    The caller owns the transaction and commit.
    """
    if not settings.embedding_enabled or settings.google_api_key is None:
        return None
    first = db.get(DocumentPageText, (document.id, 1))
    if first is None or not first.layout or first.layout.get("version") != READER_VERSION:
        return None
    existing = current_index(db, document)
    if existing is not None:
        return existing
    total = db.scalar(
        select(func.count()).select_from(EvidenceChunk).where(
            EvidenceChunk.document_id == document.id,
            EvidenceChunk.source_sha256 == document.sha256,
            EvidenceChunk.reader_version == READER_VERSION,
            EvidenceChunk.chunker_version == CHUNKER_VERSION,
        )
    ) or 0
    if not total:
        return None
    now = datetime.now(UTC)
    index = DocumentIndex(
        id=uuid4(), document_id=document.id, source_sha256=document.sha256,
        reader_version=READER_VERSION, chunker_version=CHUNKER_VERSION,
        provider="google", model=MODEL, dimensions=DIMENSIONS, format_version=FORMAT_VERSION,
        state="queued", attempts=0, lease_token=None, lease_until=None,
        dispatch_after=now, error_code=None, processed_chunks=0, total_chunks=total,
        created_at=now, completed_at=None,
    )
    db.add(index)
    return index


def dispatch_once(factory: sessionmaker[Session], publish: Callable[[str], None]) -> int:
    now = datetime.now(UTC)
    sent = 0
    with factory() as db:
        jobs = db.scalars(
            select(DocumentIndex)
            .where(
                or_(
                    (DocumentIndex.state == "queued") & (DocumentIndex.dispatch_after <= now),
                    (DocumentIndex.state == "processing") & (DocumentIndex.lease_until <= now),
                )
            )
            .order_by(DocumentIndex.dispatch_after)
            .limit(20)
            .with_for_update(skip_locked=True)
        ).all()
        for job in jobs:
            if job.state == "processing":
                job.lease_token = None
                job.lease_until = None
                job.error_code = "worker_unavailable"
                job.state = "queued" if job.attempts < MAX_FAILURES else "failed"
            if job.state != "queued":
                continue
            publish(str(job.id))
            job.dispatch_after = now + timedelta(seconds=30)
            sent += 1
        db.commit()
    return sent


def claim(
    factory: sessionmaker[Session], index_id: UUID
) -> tuple[UUID, list[tuple[str, str]]] | None:
    with factory() as db:
        index = db.get(DocumentIndex, index_id)
        if index is None:
            return None
        document = db.get(Document, index.document_id)
        if document is None:
            return None
        project = db.scalar(
            select(ResearchProject).where(ResearchProject.id == document.project_id).with_for_update()
        )
        index = db.scalar(
            select(DocumentIndex).where(DocumentIndex.id == index_id).with_for_update()
            .execution_options(populate_existing=True)
        )
        if index is None or index.state != "queued":
            return None
        if project is None or project.deleted_at is not None or document.sha256 != index.source_sha256:
            index.state = "cancelled"
            db.commit()
            return None
        if index.attempts >= MAX_FAILURES:
            index.state = "failed"
            db.commit()
            return None
        rows = db.execute(
            select(EvidenceChunk.id, EvidenceChunk.text)
            .outerjoin(
                ChunkEmbedding,
                and_(ChunkEmbedding.index_id == index_id, ChunkEmbedding.chunk_id == EvidenceChunk.id),
            )
            .where(
                EvidenceChunk.document_id == index.document_id,
                EvidenceChunk.source_sha256 == index.source_sha256,
                EvidenceChunk.reader_version == index.reader_version,
                EvidenceChunk.chunker_version == index.chunker_version,
                ChunkEmbedding.chunk_id.is_(None),
            )
            .order_by(EvidenceChunk.page_number, EvidenceChunk.id)
            .limit(MAX_BATCH)
        ).all()
        if not rows:
            count = db.scalar(
                select(func.count()).select_from(ChunkEmbedding)
                .where(ChunkEmbedding.index_id == index_id)
            ) or 0
            index.processed_chunks = count
            index.state = "ready" if count == index.total_chunks else "failed"
            index.error_code = None if count == index.total_chunks else "source_changed"
            if index.state == "ready":
                index.completed_at = datetime.now(UTC)
            db.commit()
            return None
        token = uuid4()
        index.state = "processing"
        index.attempts += 1
        index.lease_token = token
        index.lease_until = datetime.now(UTC) + timedelta(seconds=LEASE_SECONDS)
        index.error_code = None
        db.commit()
        return token, [(chunk_id, source_text) for chunk_id, source_text in rows]


def finish(
    factory: sessionmaker[Session], index_id: UUID, token: UUID,
    vectors: list[tuple[str, list[float]]] | None, failure: EmbeddingFailure | None,
) -> bool:
    with factory() as db:
        index = db.get(DocumentIndex, index_id)
        if index is None:
            return False
        document = db.get(Document, index.document_id)
        if document is None:
            return False
        project = db.scalar(
            select(ResearchProject).where(ResearchProject.id == document.project_id).with_for_update()
        )
        index = db.scalar(
            select(DocumentIndex).where(DocumentIndex.id == index_id).with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            index is None or index.state != "processing" or index.lease_token != token
            or index.lease_until is None or index.lease_until <= datetime.now(UTC)
        ):
            return False
        index.lease_token = None
        index.lease_until = None
        if project is None or project.deleted_at is not None:
            index.state = "cancelled"
        elif failure:
            index.error_code = failure.code
            index.state = (
                "queued" if failure.transient and index.attempts < MAX_FAILURES else "failed"
            )
            index.dispatch_after = datetime.now(UTC) + timedelta(seconds=30 * index.attempts)
        elif vectors is not None:
            db.execute(
                text(
                    "INSERT INTO chunk_embeddings (index_id,chunk_id,embedding) "
                    "VALUES (:index_id,:chunk_id,CAST(:embedding AS vector(768))) "
                    "ON CONFLICT DO NOTHING"
                ),
                [
                    {"index_id": index_id, "chunk_id": chunk_id, "embedding": vector_literal(vector)}
                    for chunk_id, vector in vectors
                ],
            )
            index.processed_chunks = db.scalar(
                select(func.count()).select_from(ChunkEmbedding)
                .where(ChunkEmbedding.index_id == index_id)
            ) or 0
            index.attempts = 0
            index.state = "ready" if index.processed_chunks >= index.total_chunks else "queued"
            index.dispatch_after = datetime.now(UTC)
            if index.state == "ready":
                index.completed_at = datetime.now(UTC)
        else:
            index.state = "failed"
            index.error_code = "worker_unavailable"
        db.commit()
        return True


def run_index(factory: sessionmaker[Session], settings: Settings, index_id: UUID) -> None:
    claimed = claim(factory, index_id)
    if claimed is None:
        return
    token, rows = claimed
    try:
        with GoogleEmbeddings(settings) as provider:
            vectors = provider.documents([source_text for _, source_text in rows])
        finish(factory, index_id, token, list(zip([row[0] for row in rows], vectors, strict=True)), None)
    except EmbeddingFailure as failure:
        finish(factory, index_id, token, None, failure)
    except ValueError:
        # A source chunk outside the provider contract is a terminal data issue.
        finish(factory, index_id, token, None, EmbeddingFailure("source_not_embeddable", False))
