"""Researcher-verified bibliography; exact DOI conflicts and probable title matches."""

import hashlib
import json
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
from app.modules.references import importing
from app.modules.references.models import ReferenceImport, ReferenceRecord, ReferenceSettings
from app.modules.references.schemas import (
    DuplicateMatches,
    ImportCandidate,
    ImportPreview,
    ImportPreviewInput,
    ReferenceImportInput,
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


URL_PATTERN = re.compile(r"https?://[^\s/]+(?:/[^\s]*)?", flags=re.I)


def normalize_doi(raw: str | None) -> str | None:
    """Canonical lower-case DOI, None when empty; ValueError when it is not a DOI."""
    if not raw:
        return None
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", raw.strip(), flags=re.I).casefold()
    if not re.fullmatch(r"10\.\d{4,9}/\S+", doi) or len(doi) > 260:
        raise ValueError(raw)
    return doi


def _doi(raw: str | None) -> str | None:
    try:
        return normalize_doi(raw)
    except ValueError:
        raise HTTPException(422, "Enter a valid DOI, or leave the field empty") from None


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
    if data.url and not URL_PATTERN.fullmatch(data.url):
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


def _remaining(db: Session, project_id: UUID) -> int:
    used = db.scalar(select(func.count()).select_from(ReferenceRecord).where(
        ReferenceRecord.project_id == project_id, ReferenceRecord.deleted_at.is_(None),
    )) or 0
    return max(0, MAX_REFERENCES - used)


def _candidate(db: Session, project_id: UUID, index: int, draft: importing.Draft,
               seen_dois: dict[str, str], seen_titles: dict[tuple[str, int | None], str],
               ) -> ImportCandidate:
    errors: list[str] = []
    warnings = list(draft.warnings)
    duplicate_of: UUID | None = None
    title_key = _title_key(draft.title)
    if not title_key:
        errors.append("Title is missing.")
    elif len(draft.title) > 500:
        errors.append("Title is longer than 500 characters.")
    authors = draft.authors
    if not authors:
        errors.append("No author is listed.")
    elif len(authors) > importing.MAX_AUTHORS:
        warnings.append(f"{len(authors)} authors listed; the first {importing.MAX_AUTHORS} were kept.")
        authors = authors[:importing.MAX_AUTHORS]
    if any(len(name) > 160 for name in authors):
        errors.append("An author name is longer than 160 characters.")
    if len(draft.container_title) > 500:
        errors.append("Journal or container title is longer than 500 characters.")
    url = draft.url
    if url and (len(url) > 2000 or not URL_PATTERN.fullmatch(url)):
        warnings.append("The URL is not an http or https link and was left empty.")
        url = ""
    try:
        doi = normalize_doi(draft.doi)
    except ValueError:
        warnings.append(f"“{draft.doi[:80]}” is not a recognisable DOI and was left empty.")
        doi = None
    if doi:
        existing = db.scalar(select(ReferenceRecord.id).where(
            ReferenceRecord.project_id == project_id, ReferenceRecord.doi == doi,
            ReferenceRecord.deleted_at.is_(None),
        ))
        if existing:
            errors.append("A reference with this DOI is already in the project.")
            duplicate_of = existing
        elif doi in seen_dois:
            errors.append(f"Same DOI as {seen_dois[doi]} earlier in this file.")
        else:
            seen_dois[doi] = draft.label
    if title_key and duplicate_of is None:
        probable = db.scalar(select(ReferenceRecord.id).where(
            ReferenceRecord.project_id == project_id, ReferenceRecord.deleted_at.is_(None),
            ReferenceRecord.title_key == title_key[:500], ReferenceRecord.year == draft.year,
        ).limit(1)) if draft.year is not None else None
        if probable:
            warnings.append("Probable duplicate: a reference with the same title and year is already in the project.")
            duplicate_of = probable
        elif (title_key, draft.year) in seen_titles:
            warnings.append(f"Probable duplicate of {seen_titles[(title_key, draft.year)]} earlier in this file.")
        else:
            seen_titles[(title_key, draft.year)] = draft.label
    return ImportCandidate(
        index=index, label=draft.label[:200], kind=draft.kind, title=draft.title, authors=authors,
        year=draft.year, container_title=draft.container_title, doi=doi, url=url,
        importable=not errors, errors=errors, warnings=warnings, duplicate_of=duplicate_of,
    )


def preview_import(db: Session, owner: UUID, project_id: UUID,
                   data: ImportPreviewInput) -> ImportPreview:
    owned_project(db, owner, project_id)
    try:
        drafts = (importing.parse_bibtex(data.text) if data.format == "bibtex"
                  else importing.parse_ris(data.text))
    except importing.ImportSyntaxError as error:
        raise HTTPException(422, str(error)) from None
    if not drafts:
        raise HTTPException(422, "No references were found. Check that the file matches the chosen format")
    seen_dois: dict[str, str] = {}
    seen_titles: dict[tuple[str, int | None], str] = {}
    return ImportPreview(
        items=[_candidate(db, project_id, index, draft, seen_dois, seen_titles)
               for index, draft in enumerate(drafts)],
        remaining_capacity=_remaining(db, project_id),
    )


def import_references(db: Session, owner: UUID, project_id: UUID,
                      data: ReferenceImportInput) -> ReferencePage:
    """Create reviewed records atomically; a retried request returns the original batch."""
    _editable(db, owner, project_id)
    fingerprint = hashlib.sha256(json.dumps(data.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
    previous = db.scalar(select(ReferenceImport).where(
        ReferenceImport.project_id == project_id, ReferenceImport.request_id == data.request_id,
    ))
    if previous:
        if previous.request_hash != fingerprint:
            raise HTTPException(409, "This import request ID was already used")
        saved = {str(record.id): record for record in db.scalars(select(ReferenceRecord).where(
            ReferenceRecord.id.in_([UUID(item) for item in previous.reference_ids]),
        ))}
        return ReferencePage(items=[_read(saved[item]) for item in previous.reference_ids])
    remaining = _remaining(db, project_id)
    if len(data.items) > remaining:
        raise HTTPException(409, f"Only {remaining} more references fit in this project")
    now = datetime.now(UTC)
    seen: set[str] = set()
    records: list[ReferenceRecord] = []
    for number, item in enumerate(data.items, 1):
        try:
            doi = _validate(db, project_id, item)
        except HTTPException as error:
            raise HTTPException(error.status_code, f"Item {number}: {error.detail}") from None
        if doi in seen:
            raise HTTPException(409, f"Item {number}: the same DOI appears earlier in this import")
        if doi:
            seen.add(doi)
        record = ReferenceRecord(project_id=project_id, revision=1, created_at=now,
                                 updated_at=now, deleted_at=None)
        _assign(record, item, doi)
        records.append(record)
    db.add_all(records)
    db.flush()
    db.add(ReferenceImport(project_id=project_id, request_id=data.request_id,
                           request_hash=fingerprint,
                           reference_ids=[str(record.id) for record in records], created_at=now))
    _commit(db)
    return ReferencePage(items=[_read(record) for record in records])
