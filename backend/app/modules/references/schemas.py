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
    volume: str = Field(default="", max_length=40)
    issue: str = Field(default="", max_length=40)
    pages: str = Field(default="", max_length=80)
    article_number: str = Field(default="", max_length=80)
    publisher: str = Field(default="", max_length=300)
    edition: str = Field(default="", max_length=80)
    doi: str | None = Field(default=None, max_length=260)
    url: str = Field(default="", max_length=2000)
    document_id: UUID | None = None

    @field_validator("title", "authors", "container_title", "doi", "url", "volume", "issue", "pages", "article_number", "publisher", "edition")
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


class ReferenceImportRequest(BaseModel):
    format: Literal["bibtex", "ris"]
    content: str = Field(min_length=1, max_length=100_000)


class ReferenceImportItem(BaseModel):
    kind: ReferenceKind
    title: str
    authors: list[str]
    year: int | None
    container_title: str
    volume: str
    issue: str
    pages: str
    article_number: str
    publisher: str
    edition: str
    doi: str | None
    url: str
    warnings: list[str]


class ReferenceImportPreview(BaseModel):
    format: Literal["bibtex", "ris"]
    preview_only: Literal[True]
    items: list[ReferenceImportItem]


class BibliographySegment(BaseModel):
    text: str
    italic: bool


class BibliographyEntry(BaseModel):
    reference_id: UUID
    text: str
    segments: list[BibliographySegment]
    warnings: list[str]


class Bibliography(BaseModel):
    style: CitationStyle
    style_label: str
    preview: Literal[True]
    limitations: list[str]
    items: list[BibliographyEntry]
