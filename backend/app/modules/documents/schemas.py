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


class ReaderLayout(BaseModel):
    version: str
    width: float
    height: float
    rotation: int
    words: list[WordAnchor]
    passages: list[ReadablePassage]
    figures: list[SourceFigure] = Field(default_factory=list)
    tables: list[SourceTable] = Field(default_factory=list)
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
