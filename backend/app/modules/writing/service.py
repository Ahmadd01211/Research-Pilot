"""Explicit saves create immutable, owner-scoped draft versions."""

import re
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.projects.service import owned as owned_project
from app.modules.references.models import ReferenceRecord
from app.modules.writing.models import WritingDraft, WritingVersion
from app.modules.writing.schemas import (
    DraftInput,
    DraftPage,
    DraftRead,
    DraftRemove,
    DraftUpdate,
    VersionPage,
    VersionRead,
)

MAX_DRAFTS = 20
CITATION = re.compile(
    r"\[@([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\]"
)


def _editable(db: Session, owner: UUID, project_id: UUID) -> None:
    project = owned_project(db, owner, project_id, lock=True)
    if project.archived_at is not None:
        raise HTTPException(409, "Restore the project before editing drafts")


def _draft(db: Session, owner: UUID, project_id: UUID, draft_id: UUID,
           *, lock: bool = False) -> WritingDraft:
    owned_project(db, owner, project_id)
    query = select(WritingDraft).where(
        WritingDraft.id == draft_id, WritingDraft.project_id == project_id,
        WritingDraft.deleted_at.is_(None),
    )
    draft = db.scalar(query.with_for_update() if lock else query)
    if draft is None:
        raise HTTPException(404, "Draft not found")
    return draft


def _citations(db: Session, project_id: UUID, body: str) -> list[str]:
    identifiers = re.findall(r"\[@([^\]]+)\]", body)
    if any(not CITATION.fullmatch(f"[@{item}]") for item in identifiers):
        raise HTTPException(422, "A citation marker is malformed")
    ids = list(dict.fromkeys(str(UUID(item)) for item in identifiers))
    if len(ids) > 30:
        raise HTTPException(422, "Use at most 30 references in one draft")
    if ids:
        found = set(db.scalars(select(ReferenceRecord.id).where(
            ReferenceRecord.project_id == project_id, ReferenceRecord.id.in_([UUID(item) for item in ids]),
            ReferenceRecord.deleted_at.is_(None),
        )).all())
        if len(found) != len(ids):
            raise HTTPException(422, "A cited reference is missing or no longer active")
    return ids


def _read(draft: WritingDraft) -> DraftRead:
    return DraftRead(id=draft.id, title=draft.title, body=draft.body,
                     reference_ids=[UUID(item) for item in draft.reference_ids],
                     revision=draft.revision, created_at=draft.created_at,
                     updated_at=draft.updated_at)


def list_drafts(db: Session, owner: UUID, project_id: UUID) -> DraftPage:
    owned_project(db, owner, project_id)
    drafts = db.scalars(select(WritingDraft).where(
        WritingDraft.project_id == project_id, WritingDraft.deleted_at.is_(None),
    ).order_by(WritingDraft.updated_at.desc(), WritingDraft.id.desc()).limit(MAX_DRAFTS)).all()
    return DraftPage(items=[_read(draft) for draft in drafts])


def get_draft(db: Session, owner: UUID, project_id: UUID, draft_id: UUID) -> DraftRead:
    return _read(_draft(db, owner, project_id, draft_id))


def create(db: Session, owner: UUID, project_id: UUID, data: DraftInput) -> DraftRead:
    _editable(db, owner, project_id)
    if (db.scalar(select(func.count()).select_from(WritingDraft).where(
        WritingDraft.project_id == project_id, WritingDraft.deleted_at.is_(None),
    )) or 0) >= MAX_DRAFTS:
        raise HTTPException(409, "Draft limit reached")
    refs = _citations(db, project_id, data.body)
    now = datetime.now(UTC)
    draft = WritingDraft(project_id=project_id, title=data.title, body=data.body,
                         reference_ids=refs, revision=1, created_at=now,
                         updated_at=now, deleted_at=None)
    db.add(draft)
    db.flush()
    db.add(WritingVersion(draft_id=draft.id, revision=1, title=data.title,
                          body=data.body, reference_ids=refs, created_at=now))
    db.commit()
    return _read(draft)


def update(db: Session, owner: UUID, project_id: UUID, draft_id: UUID,
           data: DraftUpdate) -> DraftRead:
    _editable(db, owner, project_id)
    draft = _draft(db, owner, project_id, draft_id, lock=True)
    if draft.revision != data.expected_revision:
        raise HTTPException(409, "This draft changed. Review the latest saved version")
    refs = _citations(db, project_id, data.body)
    draft.revision += 1
    draft.title = data.title
    draft.body = data.body
    draft.reference_ids = refs
    draft.updated_at = datetime.now(UTC)
    db.add(WritingVersion(draft_id=draft.id, revision=draft.revision, title=data.title,
                          body=data.body, reference_ids=refs, created_at=draft.updated_at))
    db.commit()
    return _read(draft)


def versions(db: Session, owner: UUID, project_id: UUID, draft_id: UUID,
             before_revision: int | None = None) -> VersionPage:
    _draft(db, owner, project_id, draft_id)
    query = select(WritingVersion).where(WritingVersion.draft_id == draft_id)
    if before_revision is not None:
        query = query.where(WritingVersion.revision < before_revision)
    items = db.scalars(query.order_by(WritingVersion.revision.desc()).limit(21)).all()
    shown = items[:20]
    return VersionPage(items=[VersionRead(revision=item.revision, title=item.title,
                             body=item.body, reference_ids=[UUID(ref) for ref in item.reference_ids],
                             created_at=item.created_at) for item in shown],
                       next_before_revision=shown[-1].revision if len(items) > 20 else None)


def remove(db: Session, owner: UUID, project_id: UUID, draft_id: UUID,
           data: DraftRemove) -> None:
    _editable(db, owner, project_id)
    draft = _draft(db, owner, project_id, draft_id, lock=True)
    if draft.revision != data.expected_revision:
        raise HTTPException(409, "This draft changed. Review the latest saved version")
    draft.deleted_at = draft.updated_at = datetime.now(UTC)
    draft.revision += 1
    db.commit()
