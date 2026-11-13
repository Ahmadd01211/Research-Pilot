"""Bounded export generation stores exact download bytes for history."""

import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from uuid import UUID

from docx import Document
from fastapi import HTTPException
from openpyxl import Workbook  # type: ignore[import-untyped]
from openpyxl.styles import Alignment, Font, PatternFill  # type: ignore[import-untyped]
from openpyxl.utils import get_column_letter  # type: ignore[import-untyped]
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.documents.models import Document as PaperDocument
from app.modules.exports.models import ExportRecord
from app.modules.exports.schemas import ExportInput, ExportPage, ExportRead
from app.modules.matrix.models import MatrixCell, MatrixRow
from app.modules.projects.service import owned as owned_project
from app.modules.references.models import ReferenceRecord
from app.modules.writing.models import WritingDraft

MAX_EXPORT_BYTES = 100 * 1024 * 1024
MAX_FILE_BYTES = 2 * 1024 * 1024


def _read(item: ExportRecord) -> ExportRead:
    return ExportRead(id=item.id, kind=item.kind, draft_id=item.draft_id,
                      filename=item.filename, sha256=item.sha256,
                      byte_size=item.byte_size, created_at=item.created_at)


def _safe_cell(value: object) -> str:
    text = str(value) if value is not None else ""
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


REFERENCE_HEADERS = ["Type", "Title", "Authors", "Year", "Journal or container", "DOI", "URL", "Linked PDF ID"]


def _references(db: Session, project_id: UUID) -> list[ReferenceRecord]:
    return list(db.scalars(select(ReferenceRecord).where(
        ReferenceRecord.project_id == project_id, ReferenceRecord.deleted_at.is_(None),
    ).order_by(ReferenceRecord.title_key, ReferenceRecord.id)).all())


def _reference_values(record: ReferenceRecord) -> tuple[object, ...]:
    return (record.kind, record.title, "; ".join(record.authors), record.year,
            record.container_title, record.doi, record.url, record.document_id)


def _reference_csv(db: Session, project_id: UUID) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(REFERENCE_HEADERS)
    for record in _references(db, project_id):
        writer.writerow([_safe_cell(item) for item in _reference_values(record)])
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


def _reference_xlsx(db: Session, project_id: UUID) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "References"
    sheet.append(REFERENCE_HEADERS)
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="17365D")
    for row, record in enumerate(_references(db, project_id), start=2):
        for column, value in enumerate(_reference_values(record), 1):
            cell = sheet.cell(row, column)
            if column == 4 and value is not None:
                cell.value = value
            else:
                cell.value = str(value) if value is not None else ""
                cell.data_type = "s"  # Preserve literal metadata; never emit formulas.
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for letter, width in zip("ABCDEFGH", (18, 52, 48, 12, 44, 32, 52, 40), strict=True):
        sheet.column_dimensions[letter].width = width
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


MATRIX_FIELDS = (("question", "Research question"), ("method", "Method"),
                 ("sample", "Sample / context"), ("finding", "Finding"),
                 ("limitation", "Limitation"))
MATRIX_HEADERS = ["Paper", "Document ID"] + [
    heading for _, label in MATRIX_FIELDS for heading in (label, f"{label} (PDF page)")
]
SOURCE_HEADERS = ["Paper", "Field", "Researcher note", "PDF page", "Source chunk ID",
                  "Source SHA-256", "Reader version", "Matrix row ID"]


def _matrix(db: Session, project_id: UUID) -> list[tuple[MatrixRow, str, dict[str, MatrixCell]]]:
    """Active rows in on-screen order with only each field's current cited note."""
    rows = db.execute(select(MatrixRow, PaperDocument.filename).join(
        PaperDocument, PaperDocument.id == MatrixRow.document_id,
    ).where(
        MatrixRow.project_id == project_id, MatrixRow.deleted_at.is_(None),
    ).order_by(MatrixRow.created_at, MatrixRow.id)).all()
    return [(row, filename, {cell.field: cell for cell in row.cells if cell.superseded_at is None})
            for row, filename in rows]


def _matrix_values(filename: str, row: MatrixRow, cells: dict[str, MatrixCell]) -> list[object]:
    values: list[object] = [filename, row.document_id]
    for field, _ in MATRIX_FIELDS:
        cell = cells.get(field)
        values += [cell.value, cell.page_number] if cell else [None, None]
    return values


def _matrix_csv(db: Session, project_id: UUID) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(MATRIX_HEADERS)
    for row, filename, cells in _matrix(db, project_id):
        writer.writerow([_safe_cell(item) for item in _matrix_values(filename, row, cells)])
    return ("﻿" + stream.getvalue()).encode("utf-8")


def _sheet(workbook: Workbook, title: str, headers: list[str], rows: list[list[object]],
           widths: list[int], numeric: set[int], freeze: str) -> None:
    sheet = workbook.create_sheet(title)
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="17365D")
    for row_number, values in enumerate(rows, start=2):
        for column, value in enumerate(values, 1):
            cell = sheet.cell(row_number, column)
            if column in numeric and value is not None:
                cell.value = value
            else:
                cell.value = str(value) if value is not None else ""
                cell.data_type = "s"  # Researcher notes stay literal text, never formulas.
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    sheet.freeze_panes = freeze
    sheet.auto_filter.ref = sheet.dimensions
    for column, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(column)].width = width


def _matrix_xlsx(db: Session, project_id: UUID) -> bytes:
    matrix = _matrix(db, project_id)
    workbook = Workbook()
    default = workbook.active
    assert default is not None
    workbook.remove(default)
    pages = {4 + 2 * index for index in range(len(MATRIX_FIELDS))}
    _sheet(workbook, "Matrix", MATRIX_HEADERS,
           [_matrix_values(filename, row, cells) for row, filename, cells in matrix],
           [36, 38] + [48, 10] * len(MATRIX_FIELDS), pages, "B2")
    labels = dict(MATRIX_FIELDS)
    sources = [[filename, labels[field], cells[field].value, cells[field].page_number,
                cells[field].chunk_id, cells[field].source_sha256, cells[field].reader_version, row.id]
               for row, filename, cells in matrix for field, _ in MATRIX_FIELDS if field in cells]
    _sheet(workbook, "Sources", SOURCE_HEADERS, sources, [36, 20, 60, 10, 30, 66, 40, 38], {4}, "A2")
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def _draft(db: Session, project_id: UUID, data: ExportInput) -> WritingDraft:
    if data.draft_id is None or data.expected_revision is None:
        raise HTTPException(422, "Choose a draft and its current revision")
    draft = db.scalar(select(WritingDraft).where(
        WritingDraft.id == data.draft_id, WritingDraft.project_id == project_id,
        WritingDraft.deleted_at.is_(None),
    ))
    if draft is None:
        raise HTTPException(404, "Draft not found")
    if draft.revision != data.expected_revision:
        raise HTTPException(409, "Draft changed. Review its latest version before exporting")
    return draft


def _draft_markdown(draft: WritingDraft) -> bytes:
    title = " ".join(draft.title.splitlines())
    return f"# {title}\n\n{draft.body.rstrip()}\n".encode()


def _draft_docx(draft: WritingDraft) -> bytes:
    document = Document()
    title = " ".join(draft.title.splitlines())
    document.core_properties.title = title
    document.add_heading(title, level=0)
    for line in draft.body.splitlines():
        if line.startswith("# "):
            document.add_heading(line[2:], level=1)
        elif line.startswith("## "):
            document.add_heading(line[3:], level=2)
        else:
            document.add_paragraph(line)
    stream = io.BytesIO()
    document.save(stream)
    return stream.getvalue()


def create(db: Session, owner: UUID, project_id: UUID, data: ExportInput) -> ExportRead:
    project = owned_project(db, owner, project_id, lock=True)
    fingerprint = hashlib.sha256(json.dumps(data.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
    existing = db.scalar(select(ExportRecord).where(
        ExportRecord.project_id == project_id, ExportRecord.request_id == data.request_id,
    ))
    if existing:
        if existing.request_hash != fingerprint:
            raise HTTPException(409, "This export request ID was already used")
        return _read(existing)
    if project.archived_at is not None:
        raise HTTPException(409, "Restore the project before creating exports")
    if data.kind in {"reference_csv", "reference_xlsx"}:
        if data.draft_id is not None or data.expected_revision is not None:
            raise HTTPException(422, "Reference exports do not use a draft")
        extension = "csv" if data.kind == "reference_csv" else "xlsx"
        content = (_reference_csv(db, project_id) if extension == "csv"
                   else _reference_xlsx(db, project_id))
        filename = f"references-{project_id.hex[:8]}.{extension}"
        mime = ("text/csv; charset=utf-8" if extension == "csv" else
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    elif data.kind in {"matrix_csv", "matrix_xlsx"}:
        if data.draft_id is not None or data.expected_revision is not None:
            raise HTTPException(422, "Matrix exports do not use a draft")
        extension = "csv" if data.kind == "matrix_csv" else "xlsx"
        content = (_matrix_csv(db, project_id) if extension == "csv"
                   else _matrix_xlsx(db, project_id))
        filename = f"matrix-{project_id.hex[:8]}.{extension}"
        mime = ("text/csv; charset=utf-8" if extension == "csv" else
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        draft = _draft(db, project_id, data)
        extension = "md" if data.kind == "draft_markdown" else "docx"
        content = _draft_markdown(draft) if extension == "md" else _draft_docx(draft)
        assert data.draft_id is not None
        filename = f"draft-{data.draft_id.hex[:8]}-v{data.expected_revision}.{extension}"
        mime = ("text/markdown; charset=utf-8" if extension == "md" else
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    if not content or len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, "Export exceeds the 2 MB file limit")
    used = db.scalar(select(func.sum(ExportRecord.byte_size)).where(
        ExportRecord.project_id == project_id,
    )) or 0
    if used + len(content) > MAX_EXPORT_BYTES:
        raise HTTPException(409, "Project export history reached its 100 MB storage limit")
    item = ExportRecord(project_id=project_id, draft_id=data.draft_id, kind=data.kind,
                        filename=filename, content_type=mime, body=content,
                        sha256=hashlib.sha256(content).hexdigest(), byte_size=len(content),
                        request_id=data.request_id, request_hash=fingerprint,
                        created_at=datetime.now(UTC))
    db.add(item)
    db.commit()
    return _read(item)


def list_exports(db: Session, owner: UUID, project_id: UUID, offset: int) -> ExportPage:
    owned_project(db, owner, project_id)
    total = db.scalar(select(func.count()).select_from(ExportRecord).where(
        ExportRecord.project_id == project_id,
    )) or 0
    items = db.scalars(select(ExportRecord).where(
        ExportRecord.project_id == project_id,
    ).order_by(ExportRecord.created_at.desc(), ExportRecord.id.desc()).offset(offset).limit(20)).all()
    return ExportPage(items=[_read(item) for item in items], total=total)


def download(db: Session, owner: UUID, project_id: UUID, export_id: UUID) -> ExportRecord:
    owned_project(db, owner, project_id)
    item = db.scalar(select(ExportRecord).where(
        ExportRecord.id == export_id, ExportRecord.project_id == project_id,
    ))
    if item is None:
        raise HTTPException(404, "Export not found")
    return item
