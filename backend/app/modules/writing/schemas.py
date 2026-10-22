from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class DraftInput(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    body: str = Field(default="", max_length=50000)

    @field_validator("title")
    @classmethod
    def clean_title(cls, title: str) -> str:
        if not title.strip():
            raise ValueError("Enter a draft title")
        return title.strip()


class DraftUpdate(DraftInput):
    expected_revision: int = Field(ge=1)


class DraftRemove(BaseModel):
    expected_revision: int = Field(ge=1)


class DraftRead(BaseModel):
    id: UUID
    title: str
    body: str
    reference_ids: list[UUID]
    revision: int
    created_at: datetime
    updated_at: datetime


class DraftPage(BaseModel):
    items: list[DraftRead]


class VersionRead(BaseModel):
    revision: int
    title: str
    body: str
    reference_ids: list[UUID]
    created_at: datetime


class VersionPage(BaseModel):
    items: list[VersionRead]
    next_before_revision: int | None
