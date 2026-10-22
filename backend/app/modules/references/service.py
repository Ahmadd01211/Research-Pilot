"""Researcher-verified bibliography; exact DOI conflicts and probable title matches."""

import re
import unicodedata
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.documents.models import Document
from app.modules.projects.service import owned as owned_project
from app.modules.references.models import ReferenceRecord, ReferenceSettings
from app.modules.references.schemas import (
    DuplicateMatches,
    ReferenceInput,
    ReferencePage,
    ReferenceRead,
    ReferenceRemove,
    ReferenceSettingsRead,
    ReferenceSettingsUpdate,
    ReferenceUpdate,
)

MAX_REFERENCES = 500


def _title_key(title: str) -> str:
    plain = unicodedata.normalize("NFKC", title).casefold()
    return " ".join(re.findall(r"\w+", plain))[:500]


def _doi(raw: str | None) -> str | None:
    if not raw:
        return None
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", raw.strip(), flags=re.I).casefold()
    if not re.fullmatch(r"10\.\d{4,9}/\S+", doi) or len(doi) > 260:
        raise HTTPException(422, "Enter a valid DOI, or leave the field empty")
    return doi


def _read(record: ReferenceRecord) -> ReferenceRead:
    return ReferenceRead.model_validate({
        "id": record.id, "kind": record.kind, "title": record.title,
        "authors": record.authors, "year": record.year,
        "container_title": record.container_title, "doi": record.doi,
        "url": record.url, "document_id": record.document_id,
        "revision": record.revision, "created_at": record.created_at,
        "updated_at": record.updated_at,
    })


def _editable(db: Session, owner: UUID, project_id: UUID) -> None:
    project = owned_project(db, owner, project_id, lock=True)
    if project.archived_at is not None:
        raise HTTPException(409, "Restore the project before editing references")


def _record(db: Session, project_id: UUID, reference_id: UUID) -> ReferenceRecord:
    record = db.scalar(select(ReferenceRecord).where(
        ReferenceRecord.id == reference_id, ReferenceRecord.project_id == project_id,
        ReferenceRecord.deleted_at.is_(None),
    ).with_for_update())
    if record is None:
        raise HTTPException(404, "Reference not found")
    return record


def _validate(db: Session, project_id: UUID, data: ReferenceInput,
              *, except_id: UUID | None = None) -> str | None:
    if not data.title or not _title_key(data.title):
        raise HTTPException(422, "Enter a meaningful title")
    if data.url and not re.fullmatch(r"https?://[^\s/]+(?:/[^\s]*)?", data.url, flags=re.I):
        raise HTTPException(422, "Use an http or https source URL")
    if data.document_id is not None and db.scalar(select(Document.id).where(
        Document.id == data.document_id, Document.project_id == project_id,
    )) is None:
        raise HTTPException(422, "Choose a PDF from this project")
    doi = _doi(data.doi)
    if doi and db.scalar(select(ReferenceRecord.id).where(
        ReferenceRecord.project_id == project_id, ReferenceRecord.doi == doi,
        ReferenceRecord.deleted_at.is_(None), ReferenceRecord.id != except_id,
    )):
        raise HTTPException(409, "A reference with this DOI already exists in the project")
    return doi


def list_references(db: Session, owner: UUID, project_id: UUID) -> ReferencePage:
    owned_project(db, owner, project_id)
    records = db.scalars(select(ReferenceRecord).where(
        ReferenceRecord.project_id == project_id, ReferenceRecord.deleted_at.is_(None),
    ).order_by(ReferenceRecord.created_at.desc(), ReferenceRecord.id.desc()).limit(MAX_REFERENCES)).all()
    return ReferencePage(items=[_read(record) for record in records])


def duplicates(db: Session, owner: UUID, project_id: UUID, title: str,
               year: int | None, exclude_id: UUID | None) -> DuplicateMatches:
    owned_project(db, owner, project_id)
    key = _title_key(title)
    if not key:
        return DuplicateMatches(items=[])
    statement = select(ReferenceRecord).where(
        ReferenceRecord.project_id == project_id, ReferenceRecord.deleted_at.is_(None),
        ReferenceRecord.title_key == key, ReferenceRecord.id != exclude_id,
    )
    if year is not None:
        statement = statement.where(ReferenceRecord.year == year)
    return DuplicateMatches(items=[_read(record) for record in db.scalars(statement.limit(10))])


def _assign(record: ReferenceRecord, data: ReferenceInput, doi: str | None) -> None:
    record.kind = data.kind
    record.title = data.title
    record.title_key = _title_key(data.title)
    record.authors = data.authors
    record.year = data.year
    record.container_title = data.container_title
    record.doi = doi
    record.url = data.url
    record.document_id = data.document_id


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A reference with this DOI already exists in the project") from None


def create(db: Session, owner: UUID, project_id: UUID, data: ReferenceInput) -> ReferenceRead:
    _editable(db, owner, project_id)
    if (db.scalar(select(func.count()).select_from(ReferenceRecord).where(
        ReferenceRecord.project_id == project_id, ReferenceRecord.deleted_at.is_(None),
    )) or 0) >= MAX_REFERENCES:
        raise HTTPException(409, "Reference limit reached")
    doi = _validate(db, project_id, data)
    now = datetime.now(UTC)
    record = ReferenceRecord(project_id=project_id, revision=1, created_at=now,
                             updated_at=now, deleted_at=None)
    _assign(record, data, doi)
    db.add(record)
    _commit(db)
    return _read(record)


def update(db: Session, owner: UUID, project_id: UUID, reference_id: UUID,
           data: ReferenceUpdate) -> ReferenceRead:
    _editable(db, owner, project_id)
    record = _record(db, project_id, reference_id)
    if record.revision != data.expected_revision:
        raise HTTPException(409, "This reference changed. Review the latest version")
    doi = _validate(db, project_id, data, except_id=reference_id)
    _assign(record, data, doi)
    record.revision += 1
    record.updated_at = datetime.now(UTC)
    _commit(db)
    return _read(record)


def remove(db: Session, owner: UUID, project_id: UUID, reference_id: UUID,
           data: ReferenceRemove) -> None:
    _editable(db, owner, project_id)
    record = _record(db, project_id, reference_id)
    if record.revision != data.expected_revision:
        raise HTTPException(409, "This reference changed. Review the latest version")
    record.deleted_at = record.updated_at = datetime.now(UTC)
    record.revision += 1
    db.commit()


def get_settings(db: Session, owner: UUID, project_id: UUID) -> ReferenceSettingsRead:
    owned_project(db, owner, project_id)
    setting = db.get(ReferenceSettings, project_id)
    return ReferenceSettingsRead(style=setting.style if setting else "apa7",
                                 revision=setting.revision if setting else 0,
                                 updated_at=setting.updated_at if setting else None)


def set_settings(db: Session, owner: UUID, project_id: UUID,
                 data: ReferenceSettingsUpdate) -> ReferenceSettingsRead:
    _editable(db, owner, project_id)
    setting = db.get(ReferenceSettings, project_id)
    if (setting.revision if setting else 0) != data.expected_revision:
        raise HTTPException(409, "Citation style changed. Review the latest setting")
    if setting is None:
        setting = ReferenceSettings(project_id=project_id, style=data.style, revision=1,
                                    updated_at=datetime.now(UTC))
        db.add(setting)
    else:
        setting.style = data.style
        setting.revision += 1
        setting.updated_at = datetime.now(UTC)
    db.commit()
    return ReferenceSettingsRead(style=data.style, revision=setting.revision,
                                 updated_at=setting.updated_at)
