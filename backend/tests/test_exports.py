"""Exports are immutable downloads with owner checks and spreadsheet-safe CSV."""

from uuid import uuid4

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
