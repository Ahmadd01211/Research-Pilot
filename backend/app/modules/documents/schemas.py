from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    filename: str
    byte_size: int
    created_at: datetime
    status: Literal["stored"] = "stored"


class UploadResult(BaseModel):
    document: DocumentRead
    duplicate: bool


class DocumentPage(BaseModel):
    items: list[DocumentRead]
    total: int
