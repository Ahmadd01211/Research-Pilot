from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
ResearchText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
ResearchItems = Annotated[list[ResearchText], Field(max_length=20)]
ProjectStatus = Literal["active", "archived", "all"]


class ProjectFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Title
    description: Description = ""
    research_questions: ResearchItems = Field(default_factory=list)
    objectives: ResearchItems = Field(default_factory=list)


class ProjectCreate(ProjectFields):
    request_id: UUID


class ProjectPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    title: Title | None = None
    description: Description | None = None
    research_questions: ResearchItems | None = None
    objectives: ResearchItems | None = None

    @field_validator("title", "description", "research_questions", "objectives")
    @classmethod
    def reject_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("Use an empty value where allowed, not null")
        return value

    @model_validator(mode="after")
    def require_change(self) -> "ProjectPatch":
        if not self.model_fields_set - {"expected_revision"}:
            raise ValueError("Provide at least one editable field")
        return self


class ProjectTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)


class ProjectRead(ProjectFields):
    model_config = ConfigDict(from_attributes=True)
    description: Description
    research_questions: ResearchItems
    objectives: ResearchItems
    id: UUID
    revision: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class ProjectPage(BaseModel):
    items: list[ProjectRead]
    next_cursor: str | None
    total: int


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    action: str
    summary: str
    changed_fields: list[str]
    created_at: datetime


class ActivityPage(BaseModel):
    items: list[ActivityRead]
    next_cursor: str | None
