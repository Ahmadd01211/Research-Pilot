"""Project invariants live here so future routes/workers share the same rules."""

import base64
import json
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_token
from app.modules.projects.models import ProjectActivity, ResearchProject
from app.modules.projects.schemas import (
    ActivityPage,
    ActivityRead,
    ProjectCreate,
    ProjectPage,
    ProjectPatch,
    ProjectRead,
    ProjectStatus,
)


def owned(
    db: Session,
    owner_id: UUID,
    project_id: UUID,
    *,
    lock: bool = False,
    include_deleted: bool = False,
) -> ResearchProject:
    # Scope in SQL, not in the UI or after returning a project to the caller.
    statement = select(ResearchProject).where(
        ResearchProject.id == project_id, ResearchProject.owner_id == owner_id
    )
    if not include_deleted:
        statement = statement.where(ResearchProject.deleted_at.is_(None))
    if lock:
        statement = statement.with_for_update()
    project = db.scalar(statement)
    if project is None:
        raise HTTPException(404, "Project not found")
    return project


def record(
    db: Session, project: ResearchProject, action: str, summary: str, fields: list[str]
) -> None:
    db.add(
        ProjectActivity(
            project_id=project.id,
            action=action,
            summary=summary,
            changed_fields=fields,
            created_at=datetime.now(UTC),
        )
    )


def create(db: Session, owner_id: UUID, data: ProjectCreate) -> ResearchProject:
    fields = data.model_dump(exclude={"request_id"})
    fingerprint = hash_token(json.dumps(fields, sort_keys=True, ensure_ascii=False))

    def replay() -> ResearchProject | None:
        existing = db.scalar(
            select(ResearchProject).where(
                ResearchProject.owner_id == owner_id,
                ResearchProject.create_request_id == data.request_id,
            )
        )
        if existing and (
            existing.create_payload_hash != fingerprint or existing.deleted_at is not None
        ):
            raise HTTPException(
                409, "This request ID was already used. Start a new project request."
            )
        return existing

    existing = replay()
    if existing:
        return existing
    now = datetime.now(UTC)
    project = ResearchProject(
        owner_id=owner_id,
        **fields,
        revision=1,
        create_request_id=data.request_id,
        create_payload_hash=fingerprint,
        created_at=now,
        updated_at=now,
        archived_at=None,
        deleted_at=None,
    )
    db.add(project)
    try:
        db.flush()  # Assign the UUID and enforce uniqueness before adding activity.
        record(db, project, "created", "Project created.", [])
        db.commit()  # Project and activity are one atomic unit.
    except IntegrityError:
        db.rollback()
        existing = replay()  # A concurrent retry may have won the unique key.
        if existing:
            return existing
        raise
    return project


def check_revision(project: ResearchProject, expected: int) -> None:
    if project.revision != expected:
        raise HTTPException(
            409,
            "This project changed. Your edits were not saved. Review the latest version before retrying.",
        )


def update(db: Session, owner_id: UUID, project_id: UUID, data: ProjectPatch) -> ResearchProject:
    project = owned(db, owner_id, project_id, lock=True)
    check_revision(project, data.expected_revision)
    if project.archived_at is not None:
        raise HTTPException(409, "Restore this archived project before editing it")
    changes = data.model_dump(exclude_unset=True, exclude={"expected_revision"})
    changed = [key for key, value in changes.items() if getattr(project, key) != value]
    if changed:
        for key in changed:
            setattr(project, key, changes[key])
        project.revision += 1
        project.updated_at = datetime.now(UTC)
        record(db, project, "updated", "Project details updated.", sorted(changed))
    db.commit()
    return project


def transition(
    db: Session,
    owner_id: UUID,
    project_id: UUID,
    expected: int,
    action: Literal["archive", "restore", "delete"],
) -> ResearchProject:
    project = owned(db, owner_id, project_id, lock=True, include_deleted=action == "delete")
    if action == "delete" and project.deleted_at is not None:
        return project  # Repeated DELETE cannot duplicate the deletion activity.
    check_revision(project, expected)
    now = datetime.now(UTC)
    changed = False
    if action == "archive" and project.archived_at is None:
        project.archived_at = now
        changed = True
    elif action == "restore" and project.archived_at is not None:
        project.archived_at = None
        changed = True
    elif action == "delete":
        project.deleted_at = now
        changed = True
    if changed:
        project.revision += 1
        project.updated_at = now
        labels = {
            "archive": ("archived", "Project archived."),
            "restore": ("restored", "Project restored."),
            "delete": ("deleted", "Project removed from the workspace. Record retained."),
        }
        verb, summary = labels[action]
        record(db, project, verb, summary, [])
    db.commit()
    return project


def encode_cursor(created_at: datetime, identity: UUID) -> str:
    return base64.urlsafe_b64encode(
        json.dumps([created_at.isoformat(), str(identity)]).encode()
    ).decode()


def decode_cursor(value: str) -> tuple[datetime, UUID]:
    try:
        data = json.loads(base64.b64decode(value, altchars=b"-_", validate=True))
        if (
            not isinstance(data, list)
            or len(data) != 2
            or not all(isinstance(v, str) for v in data)
        ):
            raise ValueError
        timestamp, identity = datetime.fromisoformat(data[0]), UUID(data[1])
        if timestamp.tzinfo is None:
            raise ValueError
        return timestamp, identity
    except (ValueError, TypeError, UnicodeError):
        raise HTTPException(400, "Invalid pagination cursor") from None


def list_projects(
    db: Session, owner_id: UUID, status: ProjectStatus, search: str, limit: int, cursor: str | None
) -> ProjectPage:
    filters = [ResearchProject.owner_id == owner_id, ResearchProject.deleted_at.is_(None)]
    if status != "all":
        filters.append(
            ResearchProject.archived_at.is_(None)
            if status == "active"
            else ResearchProject.archived_at.is_not(None)
        )
    if search:
        # User text is a literal search term, not a SQL LIKE pattern.
        term = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        filters.append(ResearchProject.title.ilike(f"%{term}%", escape="\\"))
    total = db.scalar(select(func.count()).select_from(ResearchProject).where(*filters)) or 0
    if cursor:
        created_at, identity = decode_cursor(cursor)
        filters.append(
            or_(
                ResearchProject.created_at < created_at,
                and_(ResearchProject.created_at == created_at, ResearchProject.id < identity),
            )
        )
    rows = list(
        db.scalars(
            select(ResearchProject)
            .where(*filters)
            .order_by(ResearchProject.created_at.desc(), ResearchProject.id.desc())
            .limit(limit + 1)
        )
    )
    next_cursor = (
        encode_cursor(rows[limit - 1].created_at, rows[limit - 1].id) if len(rows) > limit else None
    )
    return ProjectPage(
        items=[ProjectRead.model_validate(row) for row in rows[:limit]],
        next_cursor=next_cursor,
        total=total,
    )


def activities(
    db: Session, owner_id: UUID, project_id: UUID, limit: int, cursor: str | None
) -> ActivityPage:
    owned(db, owner_id, project_id)
    filters = [ProjectActivity.project_id == project_id]
    if cursor:
        created_at, identity = decode_cursor(cursor)
        filters.append(
            or_(
                ProjectActivity.created_at < created_at,
                and_(ProjectActivity.created_at == created_at, ProjectActivity.id < identity),
            )
        )
    rows = list(
        db.scalars(
            select(ProjectActivity)
            .where(*filters)
            .order_by(ProjectActivity.created_at.desc(), ProjectActivity.id.desc())
            .limit(limit + 1)
        )
    )
    next_cursor = (
        encode_cursor(rows[limit - 1].created_at, rows[limit - 1].id) if len(rows) > limit else None
    )
    return ActivityPage(
        items=[ActivityRead.model_validate(row) for row in rows[:limit]], next_cursor=next_cursor
    )
