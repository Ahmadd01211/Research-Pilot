"""Owner-scoped vector retrieval returning inspectable source evidence."""

import re
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.documents.embeddings import (
    FORMAT_VERSION,
    EmbeddingFailure,
    GoogleEmbeddings,
    vector_literal,
)
from app.modules.documents.indexing import current_index
from app.modules.documents.service import owned as owned_document
from app.modules.projects.service import owned as owned_project


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


class SearchResponse(BaseModel):
    hits: list[SearchHit]
    model: str
    index_format: str


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


def search(
    db: Session, owner: UUID, project_id: UUID, request: SearchRequest, settings: Settings
) -> SearchResponse:
    if not settings.embedding_enabled or settings.google_api_key is None:
        raise HTTPException(503, "Research search is not configured")
    if not request.question.strip():
        raise HTTPException(422, "Enter a research question")
    if len(set(request.document_ids)) != len(request.document_ids):
        raise HTTPException(422, "Choose each paper once")
    owned_project(db, owner, project_id)
    indexes = []
    for document_id in request.document_ids:
        document = owned_document(db, owner, project_id, document_id)
        index = current_index(db, document)
        if index is None or index.state != "ready" or index.processed_chunks != index.total_chunks:
            raise HTTPException(409, "Index the selected papers before searching")
        indexes.append(index.id)
    # Release the read transaction during the external request. Recheck ownership afterward.
    db.rollback()
    try:
        with GoogleEmbeddings(settings) as provider:
            vector = provider.question(request.question)
    except EmbeddingFailure as error:
        raise HTTPException(503 if error.transient else 502, "Search provider is unavailable") from error
    owned_project(db, owner, project_id)
    for document_id in request.document_ids:
        document = owned_document(db, owner, project_id, document_id)
        index = current_index(db, document)
        if index is None or index.id not in indexes or index.state != "ready":
            raise HTTPException(409, "A selected paper changed during search")
    candidate_limit = min(MAX_CANDIDATES, max(request.limit * CANDIDATE_MULTIPLIER, request.limit))
    statement = text(
        "WITH query_terms AS ("
        " SELECT to_tsquery('english', COALESCE(string_agg(quote_literal(term), ' | '), '')) AS query "
        " FROM unnest(tsvector_to_array(to_tsvector('english', :question))) AS terms(term)"
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
        index_format=FORMAT_VERSION,
    )
