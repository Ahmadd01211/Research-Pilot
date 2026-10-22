from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import current_user, database
from app.modules.identity.models import User
from app.modules.matrix import service
from app.modules.matrix.schemas import (
    MatrixRead,
    RowCreate,
    RowDelete,
    RowRead,
    RowUpdate,
    SourcePage,
)

router = APIRouter(prefix="/api/v1/projects/{project_id}/matrix", tags=["literature matrix"])


@router.get("", response_model=MatrixRead)
def read_matrix(project_id: UUID, user: User = Depends(current_user),
                db: Session = Depends(database)) -> MatrixRead:
    return service.list_rows(db, user.id, project_id)


@router.get("/sources", response_model=SourcePage)
def read_sources(project_id: UUID, document_id: UUID, page: int | None = Query(None, ge=1, le=300),
                 offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
                 user: User = Depends(current_user), db: Session = Depends(database)) -> SourcePage:
    return service.list_sources(db, user.id, project_id, document_id, page, offset, limit)


@router.post("", response_model=RowRead, status_code=201)
def create_row(project_id: UUID, data: RowCreate, user: User = Depends(current_user),
               db: Session = Depends(database)) -> RowRead:
    return service.create(db, user.id, project_id, data)


@router.put("/{row_id}", response_model=RowRead)
def update_row(project_id: UUID, row_id: UUID, data: RowUpdate,
               user: User = Depends(current_user), db: Session = Depends(database)) -> RowRead:
    return service.update(db, user.id, project_id, row_id, data)


@router.post("/{row_id}/remove", status_code=204)
def remove_row(project_id: UUID, row_id: UUID, data: RowDelete,
               user: User = Depends(current_user), db: Session = Depends(database)) -> None:
    service.remove(db, user.id, project_id, row_id, data)
