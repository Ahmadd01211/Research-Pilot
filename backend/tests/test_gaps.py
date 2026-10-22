"""Gap candidates are hypotheses scoped to active, cited matrix cells."""

from tests.conftest import csrf, login, register
from tests.test_matrix import setup_source


def test_gap_uncertainty_changes_when_evidence_is_challenged_or_removed(client):
    project, document_id = setup_source(client)
    base = f"/api/v1/projects/{project['id']}"
    matrix = client.post(base + "/matrix", headers=csrf(client), json={
        "document_id": document_id,
        "cells": [
            {"field": "finding", "value": "Adoption varied.", "chunk_id": "matrix-source-1"},
            {"field": "limitation", "value": "Only one survey.", "chunk_id": "matrix-source-1"},
        ],
    })
    assert matrix.status_code == 201, matrix.text
    row = matrix.json()
    cells = {item["field"]: item["id"] for item in row["cells"]}
    gaps = base + "/gaps"
    payload = {"title": "Possible context gap", "rationale": "The reviewed evidence may omit other contexts.",
        "evidence": [{"matrix_cell_id": cells["finding"], "stance": "supports"}]}
    created = client.post(gaps, headers=csrf(client), json=payload)
    assert created.status_code == 201, created.text
    gap = created.json()
    assert gap["uncertainty"] == "limited_coverage" and gap["supporting_papers"] == 1
    assert gap["evidence"][0]["page_number"] == 2
    update = client.put(gaps + "/" + gap["id"], headers=csrf(client), json={
        **payload, "expected_revision": 1,
        "evidence": [*payload["evidence"],
                     {"matrix_cell_id": cells["limitation"], "stance": "challenges"}],
    })
    assert update.status_code == 200 and update.json()["uncertainty"] == "mixed_evidence"
    assert client.put(gaps + "/" + gap["id"], headers=csrf(client), json={
        **payload, "expected_revision": 1,
    }).status_code == 409
    revised_matrix = client.put(base + "/matrix/" + row["id"], headers=csrf(client), json={
        "expected_revision": 1,
        "cells": [{"field": "finding", "value": "Revised interpretation.",
                   "chunk_id": "matrix-source-1"}],
    })
    assert revised_matrix.status_code == 200, revised_matrix.text
    assert revised_matrix.json()["cells"][0]["value"] == "Revised interpretation."
    current = client.get(gaps).json()["items"][0]
    assert current["uncertainty"] == "source_needs_review"
    assert all(item["stale"] for item in current["evidence"])
    assert client.post(base + "/matrix/" + row["id"] + "/remove", headers=csrf(client),
                       json={"expected_revision": 2}).status_code == 204


def test_gap_rejects_uncited_or_foreign_matrix_cells(client):
    project, document_id = setup_source(client)
    base = f"/api/v1/projects/{project['id']}"
    row = client.post(base + "/matrix", headers=csrf(client), json={
        "document_id": document_id,
        "cells": [{"field": "finding", "value": "A finding", "chunk_id": "matrix-source-1"}],
    }).json()
    cell_id = row["cells"][0]["id"]
    gaps = base + "/gaps"
    invalid = client.post(gaps, headers=csrf(client), json={
        "title": "Uncited gap", "rationale": "This claim has no support in the matrix.",
        "evidence": [{"matrix_cell_id": cell_id, "stance": "challenges"}],
    })
    assert invalid.status_code == 422
    duplicate = client.post(gaps, headers=csrf(client), json={
        "title": "Duplicate link", "rationale": "The same field should not be counted twice.",
        "evidence": [{"matrix_cell_id": cell_id, "stance": "supports"},
                     {"matrix_cell_id": cell_id, "stance": "supports"}],
    })
    assert duplicate.status_code == 422
    register(client, "gap-other@example.com")
    login(client, "gap-other@example.com")
    assert client.get(gaps).status_code == 404
    assert client.post(gaps, headers=csrf(client), json={
        "title": "Foreign candidate", "rationale": "Cannot use another account's matrix.",
        "evidence": [{"matrix_cell_id": cell_id, "stance": "supports"}],
    }).status_code == 404
