from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

ReferenceKind = Literal["journal", "book", "conference", "preprint", "other"]
CitationStyle = Literal["apa7", "mla9", "chicago18"]


class ReferenceInput(BaseModel):
    kind: ReferenceKind
    title: str = Field(min_length=1, max_length=500)
    authors: list[str] = Field(min_length=1, max_length=20)
    year: int | None = Field(default=None, ge=1500, le=2100)
    container_title: str = Field(default="", max_length=500)
    doi: str | None = Field(default=None, max_length=260)
    url: str = Field(default="", max_length=2000)
    document_id: UUID | None = None

    @field_validator("title", "authors", "container_title", "doi", "url")
    @classmethod
    def clean(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            authors = [item.strip() for item in value if isinstance(item, str)]
            if len(authors) != len(value) or any(not item or len(item) > 160 for item in authors):
                raise ValueError("Enter each author as a name of at most 160 characters")
            return authors
        return value


class ReferenceUpdate(ReferenceInput):
    expected_revision: int = Field(ge=1)


class ReferenceRemove(BaseModel):
    expected_revision: int = Field(ge=1)


class ReferenceRead(ReferenceInput):
    id: UUID
    revision: int
    created_at: datetime
    updated_at: datetime


class ReferencePage(BaseModel):
    items: list[ReferenceRead]


class ReferenceSettingsRead(BaseModel):
    style: CitationStyle
    revision: int
    updated_at: datetime | None


class ReferenceSettingsUpdate(BaseModel):
    style: CitationStyle
    expected_revision: int = Field(ge=0)


class DuplicateMatches(BaseModel):
    items: list[ReferenceRead]
