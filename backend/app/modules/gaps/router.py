from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import current_user, database
from app.modules.gaps import service
from app.modules.gaps.schemas import GapCreate, GapPage, GapRead, GapRemove, GapUpdate
from app.modules.identity.models import User

router = APIRouter(prefix="/api/v1/projects/{project_id}/gaps", tags=["research gaps"])


@router.get("", response_model=GapPage)
def read_gaps(project_id: UUID, user: User = Depends(current_user),
              db: Session = Depends(database)) -> GapPage:
    return service.list_gaps(db, user.id, project_id)


@router.post("", response_model=GapRead, status_code=201)
def create_gap(project_id: UUID, data: GapCreate, user: User = Depends(current_user),
               db: Session = Depends(database)) -> GapRead:
    return service.create(db, user.id, project_id, data)


@router.put("/{gap_id}", response_model=GapRead)
def update_gap(project_id: UUID, gap_id: UUID, data: GapUpdate,
               user: User = Depends(current_user), db: Session = Depends(database)) -> GapRead:
    return service.update(db, user.id, project_id, gap_id, data)


@router.post("/{gap_id}/remove", status_code=204)
def remove_gap(project_id: UUID, gap_id: UUID, data: GapRemove,
               user: User = Depends(current_user), db: Session = Depends(database)) -> None:
    service.remove(db, user.id, project_id, gap_id, data)
