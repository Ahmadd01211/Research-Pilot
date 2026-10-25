from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

ExportKind = Literal["reference_csv", "reference_xlsx", "matrix_csv", "matrix_xlsx", "draft_markdown", "draft_docx"]


class ExportInput(BaseModel):
    kind: ExportKind
    request_id: UUID
    draft_id: UUID | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class ExportRead(BaseModel):
    id: UUID
    kind: ExportKind
    draft_id: UUID | None
    filename: str
    sha256: str
    byte_size: int
    created_at: datetime


class ExportPage(BaseModel):
    items: list[ExportRead]
    total: int
