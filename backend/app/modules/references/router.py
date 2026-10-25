from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import current_user, database
from app.modules.identity.models import User
from app.modules.references import formatting, service
from app.modules.references.schemas import (
    Bibliography,
    DuplicateMatches,
    ReferenceImportPreview,
    ReferenceImportRequest,
    ReferenceInput,
    ReferencePage,
    ReferenceRead,
    ReferenceRemove,
    ReferenceSettingsRead,
    ReferenceSettingsUpdate,
    ReferenceUpdate,
)

router = APIRouter(prefix="/api/v1/projects/{project_id}/references", tags=["references"])


@router.get("", response_model=ReferencePage)
def list_references(project_id: UUID, user: User = Depends(current_user),
                    db: Session = Depends(database)) -> ReferencePage:
    return service.list_references(db, user.id, project_id)


@router.post("", response_model=ReferenceRead, status_code=201)
def create_reference(project_id: UUID, data: ReferenceInput, user: User = Depends(current_user),
                     db: Session = Depends(database)) -> ReferenceRead:
    return service.create(db, user.id, project_id, data)


@router.post("/import/preview", response_model=ReferenceImportPreview)
def preview_reference_import(project_id: UUID, data: ReferenceImportRequest,
                             user: User = Depends(current_user),
                             db: Session = Depends(database)) -> ReferenceImportPreview:
    return service.preview_import(db, user.id, project_id, data)


@router.get("/duplicates", response_model=DuplicateMatches)
def find_duplicates(project_id: UUID, title: str = Query(max_length=500),
                    year: int | None = Query(default=None, ge=1500, le=2100),
                    exclude_id: UUID | None = None, user: User = Depends(current_user),
                    db: Session = Depends(database)) -> DuplicateMatches:
    return service.duplicates(db, user.id, project_id, title, year, exclude_id)


@router.get("/bibliography", response_model=Bibliography)
def read_bibliography(project_id: UUID, user: User = Depends(current_user),
                      db: Session = Depends(database)) -> Bibliography:
    return formatting.bibliography(db, user.id, project_id)


@router.get("/settings", response_model=ReferenceSettingsRead)
def read_settings(project_id: UUID, user: User = Depends(current_user),
                  db: Session = Depends(database)) -> ReferenceSettingsRead:
    return service.get_settings(db, user.id, project_id)


@router.put("/settings", response_model=ReferenceSettingsRead)
def update_settings(project_id: UUID, data: ReferenceSettingsUpdate,
                    user: User = Depends(current_user),
                    db: Session = Depends(database)) -> ReferenceSettingsRead:
    return service.set_settings(db, user.id, project_id, data)


@router.put("/{reference_id}", response_model=ReferenceRead)
def update_reference(project_id: UUID, reference_id: UUID, data: ReferenceUpdate,
                     user: User = Depends(current_user),
                     db: Session = Depends(database)) -> ReferenceRead:
    return service.update(db, user.id, project_id, reference_id, data)


@router.post("/{reference_id}/remove", status_code=204)
def remove_reference(project_id: UUID, reference_id: UUID, data: ReferenceRemove,
                     user: User = Depends(current_user), db: Session = Depends(database)) -> None:
    service.remove(db, user.id, project_id, reference_id, data)
