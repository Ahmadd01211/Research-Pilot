from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import current_user, database
from app.modules.identity.models import User
from app.modules.projects import service
from app.modules.projects.models import ResearchProject
from app.modules.projects.schemas import (
    ActivityPage,
    ProjectCreate,
    ProjectPage,
    ProjectPatch,
    ProjectRead,
    ProjectStatus,
    ProjectTransition,
)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=201)
def create_project(
    data: ProjectCreate, user: User = Depends(current_user), db: Session = Depends(database)
) -> ResearchProject:
    return service.create(db, user.id, data)


@router.get("", response_model=ProjectPage)
def list_projects(
    status: ProjectStatus = "active",
    search: str = Query("", max_length=160),
    limit: int = Query(12, ge=1, le=50),
    cursor: str | None = Query(None, max_length=300),
    user: User = Depends(current_user),
    db: Session = Depends(database),
) -> ProjectPage:
    return service.list_projects(db, user.id, status, search.strip(), limit, cursor)


@router.get("/{project_id}", response_model=ProjectRead)
def read_project(
    project_id: UUID, user: User = Depends(current_user), db: Session = Depends(database)
) -> ResearchProject:
    return service.owned(db, user.id, project_id)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: UUID,
    data: ProjectPatch,
    user: User = Depends(current_user),
    db: Session = Depends(database),
) -> ResearchProject:
    return service.update(db, user.id, project_id, data)


@router.post("/{project_id}/archive", response_model=ProjectRead)
def archive_project(
    project_id: UUID,
    data: ProjectTransition,
    user: User = Depends(current_user),
    db: Session = Depends(database),
) -> ResearchProject:
    return service.transition(db, user.id, project_id, data.expected_revision, "archive")


@router.post("/{project_id}/restore", response_model=ProjectRead)
def restore_project(
    project_id: UUID,
    data: ProjectTransition,
    user: User = Depends(current_user),
    db: Session = Depends(database),
) -> ResearchProject:
    return service.transition(db, user.id, project_id, data.expected_revision, "restore")


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: UUID,
    data: ProjectTransition,
    user: User = Depends(current_user),
    db: Session = Depends(database),
) -> None:
    service.transition(db, user.id, project_id, data.expected_revision, "delete")


@router.get("/{project_id}/activity", response_model=ActivityPage)
def project_activity(
    project_id: UUID,
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = Query(None, max_length=300),
    user: User = Depends(current_user),
    db: Session = Depends(database),
) -> ActivityPage:
    return service.activities(db, user.id, project_id, limit, cursor)
