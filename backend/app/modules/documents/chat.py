"""Owner-scoped persisted Research Chat history with immutable answer snapshots."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.documents.models import ResearchChatThread, ResearchChatTurn
from app.modules.projects.service import owned as owned_project


class ChatThreadCreate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)


class ChatThreadSummary(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    turn_count: int


class ChatTurnRead(BaseModel):
    id: UUID
    turn_number: int
    question: str
    answer: dict[str, object]
    created_at: datetime


class ChatThreadRead(ChatThreadSummary):
    turns: list[ChatTurnRead]


def create_thread(
    db: Session, owner_id: UUID, project_id: UUID, request: ChatThreadCreate
) -> ResearchChatThread:
    project = owned_project(db, owner_id, project_id)
    if project.archived_at:
        raise HTTPException(409, "Restore the project before starting a chat")
    now = datetime.now(UTC)
    thread = ResearchChatThread(
        project_id=project_id,
        owner_id=owner_id,
        title=(request.title or "New research chat").strip() or "New research chat",
        created_at=now,
        updated_at=now,
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


def list_threads(db: Session, owner_id: UUID, project_id: UUID) -> list[ChatThreadSummary]:
    owned_project(db, owner_id, project_id)
    rows = db.execute(
        select(ResearchChatThread, func.count(ResearchChatTurn.id))
        .outerjoin(ResearchChatTurn, ResearchChatTurn.thread_id == ResearchChatThread.id)
        .where(
            ResearchChatThread.project_id == project_id,
            ResearchChatThread.owner_id == owner_id,
        )
        .group_by(ResearchChatThread.id)
        .order_by(ResearchChatThread.updated_at.desc(), ResearchChatThread.id)
        .limit(100)
    ).all()
    return [
        ChatThreadSummary(
            id=thread.id,
            title=thread.title,
            created_at=thread.created_at,
            updated_at=thread.updated_at,
            turn_count=count,
        )
        for thread, count in rows
    ]


def read_thread(
    db: Session, owner_id: UUID, project_id: UUID, thread_id: UUID
) -> ChatThreadRead:
    owned_project(db, owner_id, project_id)
    thread = db.scalar(
        select(ResearchChatThread).where(
            ResearchChatThread.id == thread_id,
            ResearchChatThread.project_id == project_id,
            ResearchChatThread.owner_id == owner_id,
        )
    )
    if thread is None:
        raise HTTPException(404, "Research chat not found")
    turns = db.scalars(
        select(ResearchChatTurn)
        .where(ResearchChatTurn.thread_id == thread.id)
        .order_by(ResearchChatTurn.turn_number)
    ).all()
    return ChatThreadRead(
        id=thread.id,
        title=thread.title,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        turn_count=len(turns),
        turns=[
            ChatTurnRead(
                id=turn.id,
                turn_number=turn.turn_number,
                question=turn.question,
                answer=turn.answer,
                created_at=turn.created_at,
            )
            for turn in turns
        ],
    )
