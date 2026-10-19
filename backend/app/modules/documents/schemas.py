from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProcessingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    state: Literal["queued", "processing", "extracted", "failed", "cancelled"]
    attempts: int
    error_code: str | None
    page_count: int | None
    extractor_version: str | None
    completed_at: datetime | None


class WordAnchor(BaseModel):
    text: str
    box: tuple[float, float, float, float]
    margin: bool


class ReadablePassage(BaseModel):
    role: Literal[
        "body",
        "abstract",
        "title",
        "authors",
        "publication_metadata",
        "affiliations",
        "correspondence",
        "funding",
    ] = "body"
    id: str
    text: str
    word_indices: list[int]


class SourceTable(BaseModel):
    box: tuple[float, float, float, float]
    rows: list[list[ReadablePassage]]
    detection: str


class FigureDiscussion(BaseModel):
    page_number: int
    passage_id: str
    text: str


class SourceFigure(BaseModel):
    id: str
    label: str
    caption: str | None
    caption_word_indices: list[int]
    box: tuple[float, float, float, float] | None
    detection: Literal["embedded_image", "source_page"]
    related_passages: list[FigureDiscussion]


class FigureRead(SourceFigure):
    document_id: UUID
    page_number: int
    reader_version: str
    source_sha256: str


class FigureList(BaseModel):
    items: list[FigureRead]


class SourceLink(BaseModel):
    id: str
    box: tuple[float, float, float, float]
    text: str
    word_indices: list[int]
    target: str | None = Field(default=None, max_length=2048)
    target_page: int | None = Field(default=None, ge=1, le=300)
    status: Literal["allowed", "blocked", "internal", "unresolved"]
    origin: Literal["annotation", "visible_url", "visible_doi"]
    source_ids: list[str]


class QualityFinding(BaseModel):
    code: str
    message: str
    severity: Literal["block", "warning"]
    scope: Literal["page", "prose", "passage", "table", "links"]


class PageQuality(BaseModel):
    version: str
    state: Literal["checked", "needs_review", "blocked"]
    findings: list[QualityFinding]
    block_page: bool
    withhold_prose: bool
    blocked_passage_ids: list[str]
    blocked_table_indices: list[int]
    eligible_units: int
    withheld_passages: int
    link_count: int


class QualityPageSummary(BaseModel):
    page_number: int
    state: Literal["checked", "needs_review", "blocked", "not_assessed"]
    findings: list[QualityFinding] = Field(default_factory=list)


class DocumentQuality(BaseModel):
    document_id: UUID
    source_sha256: str
    reader_version: str
    pages: list[QualityPageSummary]
    checked_pages: int
    review_pages: int
    blocked_pages: int
    not_assessed_pages: int
    link_count: int


class ReaderLayout(BaseModel):
    version: str
    width: float
    height: float
    rotation: int
    words: list[WordAnchor]
    passages: list[ReadablePassage]
    figures: list[SourceFigure] = Field(default_factory=list)
    tables: list[SourceTable] = Field(default_factory=list)
    links: list[SourceLink] = Field(default_factory=list)
    quality: PageQuality | None = None
    excluded_margin_text: list[str]


class EvidencePage(BaseModel):
    document_id: UUID
    page_number: int
    text: str
    layout: ReaderLayout | None = None
    reader_current: bool = True
    source_sha256: str
    extractor_version: str


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    filename: str
    byte_size: int
    created_at: datetime
    status: Literal["stored", "queued", "processing", "extracted", "failed", "cancelled"]
    processing: ProcessingRead | None


class UploadResult(BaseModel):
    document: DocumentRead
    duplicate: bool


class DocumentPage(BaseModel):
    items: list[DocumentRead]
    total: int
