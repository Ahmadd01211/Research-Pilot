"""Owner-scoped vector retrieval returning inspectable source evidence."""

import logging
import re
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.documents.chunks import CHUNKER_VERSION
from app.modules.documents.embeddings import (
    EmbeddingFailure,
    embeddings_configured,
    provider_for,
    spec_for,
    vector_literal,
)
from app.modules.documents.indexing import current_index
from app.modules.documents.models import (
    Document,
    DocumentJob,
    DocumentPageText,
    EvidenceChunk,
)
from app.modules.documents.reader import READER_VERSION
from app.modules.documents.service import owned as owned_document
from app.modules.projects.service import owned as owned_project

log = logging.getLogger(__name__)


class SearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    document_ids: list[UUID] = Field(min_length=1, max_length=10)
    limit: int = Field(default=8, ge=1, le=20)


class SearchHit(BaseModel):
    chunk_id: str
    document_id: UUID
    source_sha256: str
    reader_version: str
    page_number: int
    kind: str
    source_id: str
    text: str
    source_metadata: dict[str, object]
    distance: float


class SkippedDocument(BaseModel):
    document_id: UUID
    reason: Literal["indexing", "not_indexed", "index_failed"]


class SearchResponse(BaseModel):
    hits: list[SearchHit]
    model: str
    index_format: str
    # hybrid: vectors + keywords. keyword: embeddings are off. keyword_fallback: the
    # embedding service was unavailable, so only keyword matching ran (may miss paraphrases).
    retrieval: Literal["hybrid", "keyword", "keyword_fallback"] = "hybrid"
    # Selected papers that were not searched, and why; never silently dropped.
    skipped_documents: list[SkippedDocument] = Field(default_factory=list)


RRF_CONSTANT = 60
CANDIDATE_MULTIPLIER = 5
MAX_CANDIDATES = 100


def distinct_evidence(candidates: list[SearchHit], limit: int) -> list[SearchHit]:
    """Keep ranked evidence while suppressing repeated prose from the same source.

    Numbers and source identity are conservative boundaries: separate papers and
    table observations must remain independently inspectable.
    """
    selected: list[SearchHit] = []
    signatures: list[tuple[SearchHit, set[tuple[str, ...]], set[str]]] = []
    for hit in candidates:
        words = re.findall(r"\w+", hit.text.casefold())
        shingles = {tuple(words[i:i + 5]) for i in range(max(0, len(words) - 4))}
        numbers = set(re.findall(r"\d+(?:[.,]\d+)*", hit.text))
        duplicate = False
        for previous, prior_shingles, prior_numbers in signatures:
            if hit.document_id != previous.document_id or hit.kind != previous.kind:
                continue
            if hit.source_id == previous.source_id:
                duplicate = True
                break
            if hit.kind != "prose" or numbers != prior_numbers or not shingles:
                continue
            union = shingles | prior_shingles
            if union and len(shingles & prior_shingles) / len(union) >= 0.85:
                duplicate = True
                break
        if duplicate:
            continue
        selected.append(hit)
        signatures.append((hit, shingles, numbers))
        if len(selected) == limit:
            break
    return selected


KEYWORD_MODEL = "postgres-full-text"
KEYWORD_FORMAT = "keyword-v1"
# English stemming with OR-combined query terms ranked by cover density, the same
# lexical arm the hybrid search fuses with vectors.
QUERY_TERMS = (
    "SELECT to_tsquery('english', COALESCE(string_agg(quote_literal(term), ' | '), '')) AS query "
    "FROM unnest(tsvector_to_array(to_tsvector('english', :question))) AS terms(term)"
)


def keyword_chunk_counts(db: Session, project_id: UUID) -> dict[UUID, int]:
    """Current-version chunks per paper: what keyword search can actually search."""
    rows = db.execute(
        select(EvidenceChunk.document_id, func.count())
        .join(Document, Document.id == EvidenceChunk.document_id)
        .where(
            Document.project_id == project_id,
            EvidenceChunk.source_sha256 == Document.sha256,
            EvidenceChunk.reader_version == READER_VERSION,
            EvidenceChunk.chunker_version == CHUNKER_VERSION,
        )
        .group_by(EvidenceChunk.document_id)
    ).all()
    return {document_id: count for document_id, count in rows}


def keyword_statuses(db: Session, project_id: UUID) -> list[tuple[UUID, str, int]]:
    """Per extracted paper: ready, needs_refresh (older reader) or no_evidence."""
    counts = keyword_chunk_counts(db, project_id)
    rows = db.execute(
        select(Document.id, DocumentPageText.layout["version"].astext)
        .join(DocumentJob, DocumentJob.document_id == Document.id)
        .outerjoin(
            DocumentPageText,
            (DocumentPageText.document_id == Document.id) & (DocumentPageText.page_number == 1),
        )
        .where(Document.project_id == project_id, DocumentJob.state == "extracted")
    ).all()
    statuses = []
    for document_id, reader_version in rows:
        count = counts.get(document_id, 0)
        state = (
            "ready" if count
            else "needs_refresh" if reader_version != READER_VERSION
            else "no_evidence"
        )
        statuses.append((document_id, state, count))
    return statuses


def _keyword_search(
    db: Session, owner: UUID, project_id: UUID, request: SearchRequest
) -> SearchResponse:
    owned_project(db, owner, project_id)
    documents = [owned_document(db, owner, project_id, d) for d in request.document_ids]
    counts = keyword_chunk_counts(db, project_id)
    if any(not counts.get(document.id) for document in documents):
        raise HTTPException(409, "Extract or refresh the selected papers before searching")
    candidate_limit = min(MAX_CANDIDATES, max(request.limit * CANDIDATE_MULTIPLIER, request.limit))
    statement = text(
        f"WITH query_terms AS ({QUERY_TERMS}) "
        "SELECT c.id AS chunk_id,c.document_id,c.source_sha256,c.reader_version,"
        "c.page_number,c.kind,c.source_id,c.text,c.source_metadata,"
        # Lower is better, matching vector distance: 1 / (1 + cover-density rank).
        "1.0 / (1.0 + ts_rank_cd(to_tsvector('english', c.text), q.query)) AS distance "
        "FROM query_terms q JOIN evidence_chunks c ON to_tsvector('english', c.text) @@ q.query "
        "JOIN documents d ON d.id = c.document_id "
        "WHERE c.document_id IN :documents AND c.source_sha256 = d.sha256 "
        "AND c.reader_version = :reader AND c.chunker_version = :chunker "
        "ORDER BY distance ASC, c.id LIMIT :candidate_limit"
    ).bindparams(bindparam("documents", expanding=True))
    rows = db.execute(statement, {
        "documents": [document.id for document in documents],
        "question": request.question,
        "reader": READER_VERSION,
        "chunker": CHUNKER_VERSION,
        "candidate_limit": candidate_limit,
    }).mappings()
    return SearchResponse(
        hits=distinct_evidence([SearchHit.model_validate(dict(row)) for row in rows], request.limit),
        model=KEYWORD_MODEL,
        index_format=KEYWORD_FORMAT,
        retrieval="keyword",
    )


def search(
    db: Session, owner: UUID, project_id: UUID, request: SearchRequest, settings: Settings
) -> SearchResponse:
    if not request.question.strip():
        raise HTTPException(422, "Enter a research question")
    if len(set(request.document_ids)) != len(request.document_ids):
        raise HTTPException(422, "Choose each paper once")
    if not embeddings_configured(settings):
        return _keyword_search(db, owner, project_id, request)
    owned_project(db, owner, project_id)
    indexes = []
    ready: list[UUID] = []
    skipped: list[SkippedDocument] = []
    for document_id in request.document_ids:
        document = owned_document(db, owner, project_id, document_id)
        index = current_index(db, document, settings)
        if index is not None and index.state == "ready" and index.processed_chunks == index.total_chunks:
            indexes.append(index.id)
            ready.append(document_id)
        else:
            skipped.append(SkippedDocument(
                document_id=document_id,
                reason="not_indexed" if index is None
                else "index_failed" if index.state in {"failed", "cancelled"} else "indexing",
            ))
    if not ready:
        raise HTTPException(
            409, "None of the selected papers is ready yet: they are still indexing or not indexed."
        )
    # Release the read transaction during the external request. Recheck ownership afterward.
    db.rollback()
    try:
        with provider_for(settings) as provider:
            vector = provider.question(request.question)
    except EmbeddingFailure as error:
        if not error.transient:
            raise HTTPException(502, "Search provider returned an unusable response") from error
        # Outage: keyword matching over the same ready papers, explicitly labelled.
        log.warning("search_keyword_fallback reason=%s", error.code)
        fallback = _keyword_search(db, owner, project_id, request.model_copy(
            update={"document_ids": ready}
        ))
        return fallback.model_copy(update={
            "retrieval": "keyword_fallback", "skipped_documents": skipped,
        })
    owned_project(db, owner, project_id)
    for document_id in ready:
        document = owned_document(db, owner, project_id, document_id)
        index = current_index(db, document, settings)
        if index is None or index.id not in indexes or index.state != "ready":
            raise HTTPException(409, "A selected paper changed during search")
    candidate_limit = min(MAX_CANDIDATES, max(request.limit * CANDIDATE_MULTIPLIER, request.limit))
    statement = text(
        f"WITH query_terms AS ({QUERY_TERMS}"
        "), semantic_candidates AS ("
        " SELECT e.chunk_id, e.embedding <=> CAST(:query_vector AS vector(768)) AS distance, "
        " row_number() OVER (ORDER BY e.embedding <=> CAST(:query_vector AS vector(768)), e.chunk_id) AS rank "
        " FROM chunk_embeddings e WHERE e.index_id IN :indexes "
        " ORDER BY distance, e.chunk_id LIMIT :candidate_limit"
        "), lexical_candidates AS ("
        " SELECT c.id AS chunk_id, "
        " row_number() OVER (ORDER BY ts_rank_cd(to_tsvector('english', c.text), q.query) DESC, c.id) AS rank "
        " FROM query_terms q JOIN evidence_chunks c ON to_tsvector('english', c.text) @@ q.query "
        " JOIN chunk_embeddings e ON e.chunk_id = c.id AND e.index_id IN :indexes "
        " ORDER BY ts_rank_cd(to_tsvector('english', c.text), q.query) DESC, c.id "
        " LIMIT :candidate_limit"
        "), ranked AS ("
        " SELECT chunk_id, rank AS semantic_rank, NULL::bigint AS lexical_rank, distance, "
        " 1.0 / (:rrf_constant + rank) AS contribution FROM semantic_candidates "
        " UNION ALL "
        " SELECT chunk_id, NULL::bigint, rank, NULL::double precision, "
        " 1.0 / (:rrf_constant + rank) FROM lexical_candidates"
        "), fused AS ("
        " SELECT chunk_id, SUM(contribution) AS score, COALESCE(MIN(distance), 1.0) AS distance "
        " FROM ranked GROUP BY chunk_id"
        ") "
        "SELECT c.id AS chunk_id,c.document_id,c.source_sha256,c.reader_version,"
        "c.page_number,c.kind,c.source_id,c.text,c.source_metadata,f.distance "
        "FROM fused f JOIN evidence_chunks c ON c.id=f.chunk_id "
        "ORDER BY f.score DESC, f.distance ASC, c.id LIMIT :limit"
    ).bindparams(bindparam("indexes", expanding=True))
    rows = db.execute(
        statement,
        {
            "indexes": indexes,
            "query_vector": vector_literal(vector),
            "question": request.question,
            "candidate_limit": candidate_limit,
            "rrf_constant": RRF_CONSTANT,
            "limit": candidate_limit,
        },
    ).mappings()
    return SearchResponse(
        hits=distinct_evidence([SearchHit.model_validate(dict(row)) for row in rows], request.limit),
        model=settings.embedding_model,
        index_format=spec_for(settings).format_version,
        skipped_documents=skipped,
    )
