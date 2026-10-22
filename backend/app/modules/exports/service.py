"""Bounded export generation stores exact download bytes for history."""

import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.exports.models import ExportRecord
from app.modules.exports.schemas import ExportInput, ExportPage, ExportRead
from app.modules.projects.service import owned as owned_project
from app.modules.references.models import ReferenceRecord
from app.modules.writing.models import WritingDraft

MAX_EXPORT_BYTES = 100 * 1024 * 1024
MAX_FILE_BYTES = 2 * 1024 * 1024


def _read(item: ExportRecord) -> ExportRead:
    return ExportRead(id=item.id, kind=item.kind, draft_id=item.draft_id,
                      filename=item.filename, sha256=item.sha256,
                      byte_size=item.byte_size, created_at=item.created_at)


def _safe_cell(value: object) -> str:
    text = str(value) if value is not None else ""
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def _reference_csv(db: Session, project_id: UUID) -> bytes:
    records = db.scalars(select(ReferenceRecord).where(
        ReferenceRecord.project_id == project_id, ReferenceRecord.deleted_at.is_(None),
    ).order_by(ReferenceRecord.title_key, ReferenceRecord.id)).all()
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["Type", "Title", "Authors", "Year", "Journal or container", "DOI", "URL", "Linked PDF ID"])
    for record in records:
        writer.writerow([_safe_cell(item) for item in (
            record.kind, record.title, "; ".join(record.authors), record.year,
            record.container_title, record.doi, record.url, record.document_id,
        )])
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


def _draft_markdown(db: Session, project_id: UUID, data: ExportInput) -> bytes:
    if data.draft_id is None or data.expected_revision is None:
        raise HTTPException(422, "Choose a draft and its current revision")
    draft = db.scalar(select(WritingDraft).where(
        WritingDraft.id == data.draft_id, WritingDraft.project_id == project_id,
        WritingDraft.deleted_at.is_(None),
    ))
    if draft is None:
        raise HTTPException(404, "Draft not found")
    if draft.revision != data.expected_revision:
        raise HTTPException(409, "Draft changed. Review its latest version before exporting")
    title = " ".join(draft.title.splitlines())
    return f"# {title}\n\n{draft.body.rstrip()}\n".encode()


def create(db: Session, owner: UUID, project_id: UUID, data: ExportInput) -> ExportRead:
    project = owned_project(db, owner, project_id, lock=True)
    fingerprint = hashlib.sha256(json.dumps(data.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
    existing = db.scalar(select(ExportRecord).where(
        ExportRecord.project_id == project_id, ExportRecord.request_id == data.request_id,
    ))
    if existing:
        if existing.request_hash != fingerprint:
            raise HTTPException(409, "This export request ID was already used")
        return _read(existing)
    if project.archived_at is not None:
        raise HTTPException(409, "Restore the project before creating exports")
    if data.kind == "reference_csv":
        if data.draft_id is not None or data.expected_revision is not None:
            raise HTTPException(422, "Reference CSV does not use a draft")
        content = _reference_csv(db, project_id)
        filename = f"references-{project_id.hex[:8]}.csv"
        mime = "text/csv; charset=utf-8"
    else:
        content = _draft_markdown(db, project_id, data)
        assert data.draft_id is not None
        filename = f"draft-{data.draft_id.hex[:8]}-v{data.expected_revision}.md"
        mime = "text/markdown; charset=utf-8"
    if not content or len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, "Export exceeds the 2 MB file limit")
    used = db.scalar(select(func.sum(ExportRecord.byte_size)).where(
        ExportRecord.project_id == project_id,
    )) or 0
    if used + len(content) > MAX_EXPORT_BYTES:
        raise HTTPException(409, "Project export history reached its 100 MB storage limit")
    item = ExportRecord(project_id=project_id, draft_id=data.draft_id, kind=data.kind,
                        filename=filename, content_type=mime, body=content,
                        sha256=hashlib.sha256(content).hexdigest(), byte_size=len(content),
                        request_id=data.request_id, request_hash=fingerprint,
                        created_at=datetime.now(UTC))
    db.add(item)
    db.commit()
    return _read(item)


def list_exports(db: Session, owner: UUID, project_id: UUID, offset: int) -> ExportPage:
    owned_project(db, owner, project_id)
    total = db.scalar(select(func.count()).select_from(ExportRecord).where(
        ExportRecord.project_id == project_id,
    )) or 0
    items = db.scalars(select(ExportRecord).where(
        ExportRecord.project_id == project_id,
    ).order_by(ExportRecord.created_at.desc(), ExportRecord.id.desc()).offset(offset).limit(20)).all()
    return ExportPage(items=[_read(item) for item in items], total=total)


def download(db: Session, owner: UUID, project_id: UUID, export_id: UUID) -> ExportRecord:
    owned_project(db, owner, project_id)
    item = db.scalar(select(ExportRecord).where(
        ExportRecord.id == export_id, ExportRecord.project_id == project_id,
    ))
    if item is None:
        raise HTTPException(404, "Export not found")
    return item
