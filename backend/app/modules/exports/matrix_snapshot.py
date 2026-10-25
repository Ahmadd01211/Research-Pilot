"""Export researcher-authored matrix notes with their immutable source identity."""

import csv
import io
import json
import re
from collections.abc import Iterator, Sequence

from fastapi import HTTPException
from openpyxl import Workbook  # type: ignore[import-untyped]

from app.modules.matrix.schemas import FieldName, MatrixRead

HEADERS = ["Row ID", "Row revision", "PDF ID", "PDF filename", "Field", "Researcher note",
           "Physical PDF page", "Chunk ID", "Source SHA256", "Reader version", "Source metadata"]
FIELDS: tuple[FieldName, ...] = ("question", "method", "sample", "finding", "limitation")


def _rows(matrix: MatrixRead) -> Iterator[list[str | int]]:
    for row in matrix.items:
        for cell in row.cells:
            yield [str(row.id), row.revision, str(row.document_id), row.document_filename,
                   cell.field, cell.value, cell.page_number, cell.chunk_id, cell.source_sha256,
                   cell.reader_version, json.dumps(cell.source_metadata, sort_keys=True)]


def csv_snapshot(matrix: MatrixRead) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(HEADERS)
    for row in _rows(matrix):
        writer.writerow(["'" + value if isinstance(value, str) and
                         value.lstrip().startswith(("=", "+", "-", "@")) else value for value in row])
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


def _validate_row(values: Sequence[object]) -> None:
    for value in values:
        if isinstance(value, str):
            if len(value) > 32767:
                raise HTTPException(413, "Source metadata exceeds the Excel cell limit; use CSV")
            if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", value):
                raise HTTPException(422, "Source text contains unsupported Excel characters; use CSV")


def xlsx_snapshot(matrix: MatrixRead) -> bytes:
    workbook = Workbook()
    comparison = workbook.active
    assert comparison is not None
    comparison.title = "Literature matrix"
    comparison.append(["PDF filename", "Row revision", *[field.title() for field in FIELDS], "Row ID"])
    for row in matrix.items:
        cells = {cell.field: cell.value for cell in row.cells}
        values = [row.document_filename, row.revision,
                  *[cells.get(field, "") for field in FIELDS], str(row.id)]
        _validate_row(values)
        comparison.append(values)
    provenance = workbook.create_sheet("Source provenance")
    provenance.append(HEADERS)
    for source in _rows(matrix):
        _validate_row(source)
        provenance.append(source)
    for sheet in workbook:
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for row_cells in sheet:
            for cell in row_cells:
                if isinstance(cell.value, str):
                    cell.data_type = "s"  # Source text is literal, including formula-looking notes.
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = 32
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()
