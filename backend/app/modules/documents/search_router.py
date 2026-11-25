from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.dependencies import current_user, database, redis_for, settings_for
from app.modules.documents import budget
from app.modules.documents.answers import AnswerRequest, AnswerResponse, answer
from app.modules.documents.chat import (
    ChatThreadCreate,
    ChatThreadRead,
    ChatThreadSummary,
    create_thread,
    list_threads,
    read_thread,
)
from app.modules.documents.chunks import CHUNKER_VERSION
from app.modules.documents.embeddings import embeddings_configured, spec_for
from app.modules.documents.models import Document, DocumentIndex
from app.modules.documents.reader import READER_VERSION
from app.modules.documents.search import (
    SearchRequest,
    SearchResponse,
    keyword_statuses,
    search,
)
from app.modules.identity.models import User
from app.modules.identity.service import limit as rate_limit
from app.modules.projects.service import owned as owned_project

router = APIRouter(prefix="/api/v1/projects/{project_id}/evidence", tags=["evidence"])


class Capabilities(BaseModel):
    embedding_enabled: bool
    # local: vectors computed on this server; google: chunk text is sent to Google.
    embedding_provider: Literal["google", "local"]
    answer_enabled: bool
    answer_model: str
    search_mode: Literal["hybrid", "keyword"]
    answer_provider: Literal["google", "openrouter"]
    answer_daily_limit: int
    answer_user_daily_limit: int
    answers_remaining_today: int | None
    # openrouter: whether routing may use hosts that collect prompts; google: account terms.
    answer_data_policy: Literal["no_collection", "collection_allowed", "provider_terms"]


class IndexStatus(BaseModel):
    document_id: UUID
    state: str
    processed_chunks: int
    total_chunks: int
    error_code: str | None
    search_mode: Literal["hybrid", "keyword"] = "hybrid"


class IndexStatuses(BaseModel):
    items: list[IndexStatus]


class ChatThreadList(BaseModel):
    items: list[ChatThreadSummary]


@router.get("/capabilities", response_model=Capabilities)
def capabilities(
    project_id: UUID, user: User = Depends(current_user),
    db: Session = Depends(database), settings: Settings = Depends(settings_for),
    redis: Redis = Depends(redis_for),
) -> Capabilities:
    owned_project(db, user.id, project_id)
    answers_on = bool(settings.answer_enabled and settings.answer_key)
    remaining = None
    if answers_on:
        try:
            remaining = budget.remaining(redis, settings)
        except RedisError:
            # Keyword search needs no Redis; an unknown allowance must not hide it.
            remaining = None
    return Capabilities(
        embedding_enabled=embeddings_configured(settings),
        embedding_provider=settings.embedding_provider,
        answer_enabled=answers_on,
        answer_model=settings.answer_model,
        search_mode="hybrid" if embeddings_configured(settings) else "keyword",
        answer_provider=settings.answer_provider,
        answer_daily_limit=settings.answer_daily_limit,
        answer_user_daily_limit=settings.answer_user_limit,
        answers_remaining_today=remaining,
        answer_data_policy=(
            "provider_terms" if settings.answer_provider == "google"
            else "collection_allowed" if settings.openrouter_allow_data_collection
            else "no_collection"
        ),
    )


@router.get("/indexes", response_model=IndexStatuses)
def index_statuses(
    project_id: UUID, user: User = Depends(current_user), db: Session = Depends(database),
    settings: Settings = Depends(settings_for),
) -> IndexStatuses:
    owned_project(db, user.id, project_id)
    if not embeddings_configured(settings):
        # Keyword search reads current-version chunks directly; no external index exists.
        return IndexStatuses(items=[
            IndexStatus(document_id=document_id, state=state, processed_chunks=count,
                        total_chunks=count, error_code=None, search_mode="keyword")
            for document_id, state, count in keyword_statuses(db, project_id)
        ])
    spec = spec_for(settings)
    rows = db.scalars(
        select(DocumentIndex).join(Document, Document.id == DocumentIndex.document_id).where(
            Document.project_id == project_id,
            Document.sha256 == DocumentIndex.source_sha256,
            DocumentIndex.reader_version == READER_VERSION,
            DocumentIndex.chunker_version == CHUNKER_VERSION,
            DocumentIndex.provider == spec.provider,
            DocumentIndex.model == spec.model,
            DocumentIndex.dimensions == spec.dimensions,
            DocumentIndex.format_version == spec.format_version,
        )
    ).all()
    return IndexStatuses(items=[IndexStatus.model_validate({
        "document_id": row.document_id, "state": row.state,
        "processed_chunks": row.processed_chunks, "total_chunks": row.total_chunks,
        "error_code": row.error_code,
    }) for row in rows])


@router.post("/search", response_model=SearchResponse)
def search_evidence(
    project_id: UUID, request: SearchRequest,
    user: User = Depends(current_user), db: Session = Depends(database),
    settings: Settings = Depends(settings_for),
) -> SearchResponse:
    return search(db, user.id, project_id, request, settings)


@router.post("/answer", response_model=AnswerResponse)
def answer_from_evidence(
    project_id: UUID, request: AnswerRequest,
    user: User = Depends(current_user), db: Session = Depends(database),
    settings: Settings = Depends(settings_for), redis: Redis = Depends(redis_for),
) -> AnswerResponse:
    if settings.answer_enabled and settings.answer_key:
        rate_limit(redis, settings, "research_answer", str(user.id), 10)
    return answer(db, user.id, project_id, request, settings, redis)


@router.get("/threads", response_model=ChatThreadList)
def chat_threads(
    project_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(database),
) -> ChatThreadList:
    return ChatThreadList(items=list_threads(db, user.id, project_id))


@router.post("/threads", response_model=ChatThreadSummary, status_code=201)
def new_chat_thread(
    project_id: UUID,
    request: ChatThreadCreate,
    user: User = Depends(current_user),
    db: Session = Depends(database),
) -> ChatThreadSummary:
    thread = create_thread(db, user.id, project_id, request)
    return ChatThreadSummary(
        id=thread.id,
        title=thread.title,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        turn_count=0,
    )


@router.get("/threads/{thread_id}", response_model=ChatThreadRead)
def chat_thread(
    project_id: UUID,
    thread_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(database),
) -> ChatThreadRead:
    return read_thread(db, user.id, project_id, thread_id)
