from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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


class ReaderLayout(BaseModel):
    version: str
    width: float
    height: float
    rotation: int
    words: list[WordAnchor]
    passages: list[ReadablePassage]
    excluded_margin_text: list[str]


class EvidencePage(BaseModel):
    document_id: UUID
    page_number: int
    text: str
    layout: ReaderLayout | None = None
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
