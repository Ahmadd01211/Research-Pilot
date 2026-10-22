from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

FieldName = Literal["question", "method", "sample", "finding", "limitation"]


class CellInput(BaseModel):
    field: FieldName
    value: str = Field(min_length=1, max_length=2000)
    chunk_id: str = Field(min_length=1, max_length=64)

    @field_validator("value")
    @classmethod
    def meaningful_value(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A matrix note cannot be blank")
        return value.strip()


class RowCreate(BaseModel):
    document_id: UUID
    cells: list[CellInput] = Field(min_length=1, max_length=5)


class RowUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    cells: list[CellInput] = Field(min_length=1, max_length=5)


class RowDelete(BaseModel):
    expected_revision: int = Field(ge=1)


class CellRead(BaseModel):
    id: UUID
    field: FieldName
    value: str
    chunk_id: str
    source_sha256: str
    reader_version: str
    page_number: int
    kind: str
    source_metadata: dict[str, object]


class RowRead(BaseModel):
    id: UUID
    document_id: UUID
    document_filename: str
    revision: int
    created_at: datetime
    updated_at: datetime
    cells: list[CellRead]


class MatrixRead(BaseModel):
    items: list[RowRead]


class SourceRead(BaseModel):
    chunk_id: str
    page_number: int
    kind: str
    text: str
    source_sha256: str
    reader_version: str
    source_metadata: dict[str, object]


class SourcePage(BaseModel):
    items: list[SourceRead]
    total: int
