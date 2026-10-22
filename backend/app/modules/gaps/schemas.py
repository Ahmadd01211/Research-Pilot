from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

Stance = Literal["supports", "challenges"]
Uncertainty = Literal[
    "limited_coverage", "candidate_across_papers", "mixed_evidence", "source_needs_review"
]


class EvidenceInput(BaseModel):
    matrix_cell_id: UUID
    stance: Stance


class GapCreate(BaseModel):
    title: str = Field(min_length=5, max_length=160)
    rationale: str = Field(min_length=10, max_length=2000)
    evidence: list[EvidenceInput] = Field(min_length=1, max_length=12)

    @field_validator("title", "rationale")
    @classmethod
    def trim(cls, value: str) -> str:
        if len(value.strip()) < 5:
            raise ValueError("Write a meaningful title or rationale")
        return value.strip()


class GapUpdate(GapCreate):
    expected_revision: int = Field(ge=1)


class GapRemove(BaseModel):
    expected_revision: int = Field(ge=1)


class EvidenceRead(BaseModel):
    matrix_cell_id: UUID
    stance: Stance
    field: str
    value: str
    document_id: UUID
    document_filename: str
    page_number: int
    source_sha256: str
    reader_version: str
    kind: str
    source_metadata: dict[str, object]
    stale: bool


class GapRead(BaseModel):
    id: UUID
    title: str
    rationale: str
    revision: int
    created_at: datetime
    updated_at: datetime
    uncertainty: Uncertainty
    supporting_papers: int
    evidence: list[EvidenceRead]


class GapPage(BaseModel):
    items: list[GapRead]
