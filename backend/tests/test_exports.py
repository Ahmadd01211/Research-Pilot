"""Exports are immutable downloads with owner checks and spreadsheet-safe CSV."""

import io
from uuid import uuid4

from docx import Document
from openpyxl import load_workbook

from tests.conftest import csrf, login, register
from tests.test_matrix import setup_source


def test_reference_csv_snapshot_is_safe_and_immutable(client):
    project, document_id = setup_source(client)
    base = f"/api/v1/projects/{project['id']}"
    reference = client.post(base + "/references", headers=csrf(client), json={
        "kind": "journal", "title": "=SUM(1,1)", "authors": ["A. Scholar"],
        "year": 2024, "container_title": "Research Journal", "doi": None,
        "url": "", "document_id": document_id,
    })
    assert reference.status_code == 201, reference.text
    request = {"kind": "reference_csv", "request_id": str(uuid4())}
    created = client.post(base + "/exports", headers=csrf(client), json=request)
    assert created.status_code == 201, created.text
    item = created.json()
    download = client.get(base + "/exports/" + item["id"] + "/download")
    assert download.status_code == 200
    assert b"'=SUM(1,1)" in download.content
    assert download.headers["content-disposition"].startswith("attachment;")
    assert client.post(base + "/exports", headers=csrf(client), json=request).json()["id"] == item["id"]
    assert client.post(base + "/exports", headers=csrf(client), json={
        **request, "kind": "draft_markdown",
    }).status_code == 409
    ref = reference.json()
    assert client.put(base + "/references/" + ref["id"], headers=csrf(client), json={
        "kind": "journal", "title": "Safe revised title", "authors": ["A. Scholar"],
        "year": 2024, "container_title": "Research Journal", "doi": None,
        "url": "", "document_id": document_id, "expected_revision": 1,
    }).status_code == 200
    assert client.get(base + "/exports/" + item["id"] + "/download").content == download.content
    assert client.get(base + "/exports").json()["items"][0]["id"] == item["id"]


def test_draft_export_rejects_stale_revision_and_foreign_access(client):
    project, _ = setup_source(client)
    base = f"/api/v1/projects/{project['id']}"
    draft = client.post(base + "/drafts", headers=csrf(client), json={
        "title": "Review", "body": "# Introduction\nResearcher text.",
    }).json()
    export = {"kind": "draft_markdown", "request_id": str(uuid4()),
              "draft_id": draft["id"], "expected_revision": 1}
    created = client.post(base + "/exports", headers=csrf(client), json=export)
    assert created.status_code == 201, created.text
    item = created.json()
    assert b"Researcher text." in client.get(base + "/exports/" + item["id"] + "/download").content
    assert client.put(base + "/drafts/" + draft["id"], headers=csrf(client), json={
        "title": "Revised", "body": "Revised text", "expected_revision": 1,
    }).status_code == 200
    assert client.post(base + "/exports", headers=csrf(client), json={
        **export, "request_id": str(uuid4()),
    }).status_code == 409
    register(client, "export-other@example.com")
    login(client, "export-other@example.com")
    assert client.get(base + "/exports").status_code == 404
    assert client.get(base + "/exports/" + item["id"] + "/download").status_code == 404


def test_xlsx_reference_snapshot_preserves_literal_cells_and_original_bytes(client):
    project, _ = setup_source(client)
    base = f"/api/v1/projects/{project['id']}"
    reference = client.post(base + "/references", headers=csrf(client), json={
        "kind": "journal", "title": "=SUM(1,1)", "authors": ["Scholar, Ada"],
        "year": 2024, "container_title": "Research Journal", "doi": None,
        "url": "", "document_id": None,
    })
    assert reference.status_code == 201, reference.text
    payload = {"kind": "reference_xlsx", "request_id": str(uuid4())}
    created = client.post(base + "/exports", headers=csrf(client), json=payload)
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["filename"].endswith(".xlsx")
    downloaded = client.get(base + "/exports/" + item["id"] + "/download")
    assert downloaded.status_code == 200
    sheet = load_workbook(io.BytesIO(downloaded.content), read_only=False).active
    assert sheet["B2"].value == "=SUM(1,1)"
    assert sheet["B2"].data_type == "s"
    assert sheet["D2"].value == 2024
    assert sheet.freeze_panes == "A2"
    assert client.post(base + "/exports", headers=csrf(client), json=payload).json()["id"] == item["id"]
    assert client.put(base + "/references/" + reference.json()["id"], headers=csrf(client), json={
        "kind": "journal", "title": "Updated", "authors": ["Scholar, Ada"],
        "year": 2024, "container_title": "Research Journal", "doi": None,
        "url": "", "document_id": None, "expected_revision": 1,
    }).status_code == 200
    assert client.get(base + "/exports/" + item["id"] + "/download").content == downloaded.content


def test_docx_draft_snapshot_is_readable_and_revision_checked(client):
    project, _ = setup_source(client)
    base = f"/api/v1/projects/{project['id']}"
    draft = client.post(base + "/drafts", headers=csrf(client), json={
        "title": "Review", "body": "# Introduction\nResearcher text.",
    }).json()
    payload = {"kind": "draft_docx", "request_id": str(uuid4()),
               "draft_id": draft["id"], "expected_revision": 1}
    created = client.post(base + "/exports", headers=csrf(client), json=payload)
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["filename"].endswith(".docx")
    downloaded = client.get(base + "/exports/" + item["id"] + "/download")
    assert downloaded.status_code == 200
    document = Document(io.BytesIO(downloaded.content))
    assert [paragraph.text for paragraph in document.paragraphs] == [
        "Review", "Introduction", "Researcher text.",
    ]
    assert document.paragraphs[1].style.name == "Heading 1"
    assert client.put(base + "/drafts/" + draft["id"], headers=csrf(client), json={
        "title": "Updated", "body": "New body", "expected_revision": 1,
    }).status_code == 200
    assert client.post(base + "/exports", headers=csrf(client), json={
        **payload, "request_id": str(uuid4()),
    }).status_code == 409
    assert client.get(base + "/exports/" + item["id"] + "/download").content == downloaded.content


def test_matrix_snapshots_keep_layout_provenance_and_literal_notes(client):
    project, document_id = setup_source(client)
    base = f"/api/v1/projects/{project['id']}"
    row = client.post(base + "/matrix", headers=csrf(client), json={
        "document_id": document_id, "cells": [
            {"field": "method", "value": "Survey of firms", "chunk_id": "matrix-source-1"},
            {"field": "finding", "value": "=HYPERLINK(\"x\")", "chunk_id": "matrix-source-1"},
        ],
    })
    assert row.status_code == 201, row.text
    assert client.post(base + "/exports", headers=csrf(client), json={
        "kind": "matrix_csv", "request_id": str(uuid4()),
        "draft_id": str(uuid4()), "expected_revision": 1,
    }).status_code == 422
    payload = {"kind": "matrix_csv", "request_id": str(uuid4())}
    created = client.post(base + "/exports", headers=csrf(client), json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["filename"].startswith("matrix-")
    csv_bytes = client.get(base + "/exports/" + created.json()["id"] + "/download").content
    lines = csv_bytes.decode("utf-8-sig").splitlines()
    assert lines[0].startswith("Paper,Document ID,Research question,Research question (PDF page),Method")
    assert "Survey of firms,2" in lines[1]
    assert "'=HYPERLINK" in lines[1]
    assert client.post(base + "/exports", headers=csrf(client), json=payload).json()["id"] == created.json()["id"]

    workbook_export = client.post(base + "/exports", headers=csrf(client), json={
        "kind": "matrix_xlsx", "request_id": str(uuid4()),
    })
    assert workbook_export.status_code == 201, workbook_export.text
    xlsx_bytes = client.get(base + "/exports/" + workbook_export.json()["id"] + "/download").content
    workbook = load_workbook(io.BytesIO(xlsx_bytes))
    assert workbook.sheetnames == ["Matrix", "Sources"]
    matrix = workbook["Matrix"]
    assert matrix["E2"].value == "Survey of firms" and matrix["F2"].value == 2
    assert matrix["C2"].value is None and matrix["I2"].data_type == "s"
    assert matrix["I2"].value == "=HYPERLINK(\"x\")"
    sources = [[cell.value for cell in line] for line in workbook["Sources"].iter_rows(min_row=2)]
    assert [line[1] for line in sources] == ["Method", "Finding"]
    assert sources[0][3:6] == [2, "matrix-source-1", sources[0][5]] and len(sources[0][5]) == 64

    assert client.put(base + "/matrix/" + row.json()["id"], headers=csrf(client), json={
        "expected_revision": 1,
        "cells": [{"field": "limitation", "value": "Small sample", "chunk_id": "matrix-source-1"}],
    }).status_code == 200
    assert client.get(base + "/exports/" + created.json()["id"] + "/download").content == csv_bytes
    fresh = client.post(base + "/exports", headers=csrf(client), json={
        "kind": "matrix_csv", "request_id": str(uuid4()),
    }).json()
    fresh_csv = client.get(base + "/exports/" + fresh["id"] + "/download").content.decode("utf-8-sig")
    assert "Small sample" in fresh_csv and "Survey of firms" not in fresh_csv
