from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.dependencies import current_user, database, redis_for, settings_for
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
from app.modules.documents.embeddings import DIMENSIONS, FORMAT_VERSION, MODEL
from app.modules.documents.models import Document, DocumentIndex
from app.modules.documents.reader import READER_VERSION
from app.modules.documents.search import SearchRequest, SearchResponse, search
from app.modules.identity.models import User
from app.modules.identity.service import limit as rate_limit
from app.modules.projects.service import owned as owned_project

router = APIRouter(prefix="/api/v1/projects/{project_id}/evidence", tags=["evidence"])


class Capabilities(BaseModel):
    embedding_enabled: bool
    answer_enabled: bool
    answer_model: str


class IndexStatus(BaseModel):
    document_id: UUID
    state: str
    processed_chunks: int
    total_chunks: int
    error_code: str | None


class IndexStatuses(BaseModel):
    items: list[IndexStatus]


class ChatThreadList(BaseModel):
    items: list[ChatThreadSummary]


@router.get("/capabilities", response_model=Capabilities)
def capabilities(
    project_id: UUID, user: User = Depends(current_user),
    db: Session = Depends(database), settings: Settings = Depends(settings_for),
) -> Capabilities:
    owned_project(db, user.id, project_id)
    enabled = bool(
        settings.embedding_enabled and settings.google_api_key
        and settings.google_api_key.get_secret_value().strip()
    )
    return Capabilities(embedding_enabled=enabled,
                        answer_enabled=bool(enabled and settings.answer_enabled),
                        answer_model=settings.answer_model)


@router.get("/indexes", response_model=IndexStatuses)
def index_statuses(
    project_id: UUID, user: User = Depends(current_user), db: Session = Depends(database),
) -> IndexStatuses:
    owned_project(db, user.id, project_id)
    rows = db.scalars(
        select(DocumentIndex).join(Document, Document.id == DocumentIndex.document_id).where(
            Document.project_id == project_id,
            Document.sha256 == DocumentIndex.source_sha256,
            DocumentIndex.reader_version == READER_VERSION,
            DocumentIndex.chunker_version == CHUNKER_VERSION,
            DocumentIndex.provider == "google",
            DocumentIndex.model == MODEL,
            DocumentIndex.dimensions == DIMENSIONS,
            DocumentIndex.format_version == FORMAT_VERSION,
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
    if settings.answer_enabled and settings.embedding_enabled:
        rate_limit(redis, settings, "research_answer", str(user.id), 10)
    return answer(db, user.id, project_id, request, settings)


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
