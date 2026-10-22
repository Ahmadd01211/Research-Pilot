"""Matrix rows retain field-level evidence and enforce project ownership."""

from uuid import UUID

from app.modules.documents.chunks import CHUNKER_VERSION
from app.modules.documents.models import Document, EvidenceChunk
from app.modules.documents.reader import READER_VERSION
from tests.conftest import csrf, login, register
from tests.test_documents import upload
from tests.test_projects import authenticated, create


def setup_source(client):
    authenticated(client)
    project = create(client)
    document_id = UUID(upload(client, project["id"]).json()["document"]["id"])
    with client.app.state.session_factory() as db:
        document = db.get(Document, document_id)
        assert document is not None
        db.add(EvidenceChunk(
            id="matrix-source-1", document_id=document_id,
            source_sha256=document.sha256, reader_version=READER_VERSION,
            chunker_version=CHUNKER_VERSION, page_number=2, kind="prose",
            source_id="passage-1", text="The authors surveyed firms.",
            source_metadata={"passage_id": "passage-1"},
        ))
        db.commit()
    return project, str(document_id)


def test_matrix_create_edit_and_retained_source(client):
    project, document_id = setup_source(client)
    base = f"/api/v1/projects/{project['id']}/matrix"
    sources = client.get(base + "/sources", params={"document_id": document_id, "page": 2})
    assert sources.status_code == 200 and sources.json()["total"] == 1
    input_row = {"document_id": document_id, "cells": [{
        "field": "method", "value": "Survey of firms", "chunk_id": "matrix-source-1",
    }]}
    created = client.post(base, headers=csrf(client), json=input_row)
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["cells"][0]["page_number"] == 2
    assert row["cells"][0]["source_metadata"]["passage_id"] == "passage-1"
    assert len(client.get(base).json()["items"]) == 1
    path = base + "/" + row["id"]
    revised = client.put(path, headers=csrf(client), json={"expected_revision": 1, "cells": [{
        "field": "finding", "value": "Firm adoption was measured", "chunk_id": "matrix-source-1",
    }]})
    assert revised.status_code == 200 and revised.json()["revision"] == 2
    assert [cell["field"] for cell in revised.json()["cells"]] == ["finding"]
    assert client.put(path, headers=csrf(client), json={"expected_revision": 1,
        "cells": input_row["cells"]}).status_code == 409
    assert client.post(path + "/remove", headers=csrf(client),
                       json={"expected_revision": 2}).status_code == 204
    assert client.get(base).json()["items"] == []


def test_matrix_rejects_foreign_or_mismatched_sources(client):
    project, document_id = setup_source(client)
    base = f"/api/v1/projects/{project['id']}/matrix"
    other_doc = upload(client, project["id"], content=b"%PDF-1.4\nother\n%%EOF").json()["document"]["id"]
    invalid = client.post(base, headers=csrf(client), json={"document_id": other_doc,
        "cells": [{"field": "finding", "value": "Claim", "chunk_id": "matrix-source-1"}]})
    assert invalid.status_code == 422
    duplicate = client.post(base, headers=csrf(client), json={"document_id": document_id,
        "cells": [{"field": "finding", "value": "One", "chunk_id": "matrix-source-1"},
                  {"field": "finding", "value": "Two", "chunk_id": "matrix-source-1"}]})
    assert duplicate.status_code == 422
    blank = client.post(base, headers=csrf(client), json={"document_id": document_id,
        "cells": [{"field": "finding", "value": "   ", "chunk_id": "matrix-source-1"}]})
    assert blank.status_code == 422
    assert client.get(base).json()["items"] == []
    register(client, "other-researcher@example.com")
    login(client, "other-researcher@example.com")
    assert client.get(base).status_code == 404
    assert client.get(base + "/sources", params={"document_id": document_id}).status_code == 404
