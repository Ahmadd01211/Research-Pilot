from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.core.dependencies import current_user, database
from app.modules.exports import service
from app.modules.exports.schemas import ExportInput, ExportPage, ExportRead
from app.modules.identity.models import User

router = APIRouter(prefix="/api/v1/projects/{project_id}/exports", tags=["exports"])


@router.get("", response_model=ExportPage)
def list_exports(project_id: UUID, offset: int = Query(default=0, ge=0, le=10000),
                 user: User = Depends(current_user), db: Session = Depends(database)) -> ExportPage:
    return service.list_exports(db, user.id, project_id, offset)


@router.post("", response_model=ExportRead, status_code=201)
def create_export(project_id: UUID, data: ExportInput, user: User = Depends(current_user),
                  db: Session = Depends(database)) -> ExportRead:
    return service.create(db, user.id, project_id, data)


@router.get("/{export_id}/download")
def download_export(project_id: UUID, export_id: UUID, user: User = Depends(current_user),
                    db: Session = Depends(database)) -> Response:
    item = service.download(db, user.id, project_id, export_id)
    return Response(content=item.body, media_type=item.content_type,
                    headers={"Content-Disposition": f'attachment; filename="{item.filename}"'})
