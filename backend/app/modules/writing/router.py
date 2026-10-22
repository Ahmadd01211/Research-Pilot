from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import current_user, database
from app.modules.identity.models import User
from app.modules.writing import service
from app.modules.writing.schemas import (
    DraftInput,
    DraftPage,
    DraftRead,
    DraftRemove,
    DraftUpdate,
    VersionPage,
)

router = APIRouter(prefix="/api/v1/projects/{project_id}/drafts", tags=["writing"])


@router.get("", response_model=DraftPage)
def list_drafts(project_id: UUID, user: User = Depends(current_user),
                db: Session = Depends(database)) -> DraftPage:
    return service.list_drafts(db, user.id, project_id)


@router.post("", response_model=DraftRead, status_code=201)
def create_draft(project_id: UUID, data: DraftInput, user: User = Depends(current_user),
                 db: Session = Depends(database)) -> DraftRead:
    return service.create(db, user.id, project_id, data)


@router.get("/{draft_id}", response_model=DraftRead)
def get_draft(project_id: UUID, draft_id: UUID, user: User = Depends(current_user),
              db: Session = Depends(database)) -> DraftRead:
    return service.get_draft(db, user.id, project_id, draft_id)


@router.put("/{draft_id}", response_model=DraftRead)
def update_draft(project_id: UUID, draft_id: UUID, data: DraftUpdate,
                 user: User = Depends(current_user), db: Session = Depends(database)) -> DraftRead:
    return service.update(db, user.id, project_id, draft_id, data)


@router.get("/{draft_id}/versions", response_model=VersionPage)
def list_versions(project_id: UUID, draft_id: UUID,
                  before_revision: int | None = Query(default=None, ge=1),
                  user: User = Depends(current_user),
                  db: Session = Depends(database)) -> VersionPage:
    return service.versions(db, user.id, project_id, draft_id, before_revision)


@router.post("/{draft_id}/remove", status_code=204)
def remove_draft(project_id: UUID, draft_id: UUID, data: DraftRemove,
                 user: User = Depends(current_user), db: Session = Depends(database)) -> None:
    service.remove(db, user.id, project_id, draft_id, data)
