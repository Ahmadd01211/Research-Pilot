"""Researcher-authored drafts retain provenance and immutable revisions."""

from tests.conftest import csrf, login, register
from tests.test_matrix import setup_source


def test_draft_versions_and_citation_scope(client):
    project, document_id = setup_source(client)
    base = f"/api/v1/projects/{project['id']}"
    ref = client.post(base + "/references", headers=csrf(client), json={
        "kind": "journal", "title": "Verified source", "authors": ["A. Scholar"],
        "year": 2024, "container_title": "Research Journal", "doi": None,
        "url": "", "document_id": document_id,
    })
    assert ref.status_code == 201, ref.text
    ref_id = ref.json()["id"]
    drafts = base + "/drafts"
    created = client.post(drafts, headers=csrf(client), json={
        "title": "Literature review", "body": f"# Findings\nA sourced claim [@{ref_id}].",
    })
    assert created.status_code == 201, created.text
    draft = created.json()
    assert draft["reference_ids"] == [ref_id] and draft["revision"] == 1
    updated = client.put(drafts + "/" + draft["id"], headers=csrf(client), json={
        "title": "Revised review", "body": "# Findings\nRevised by researcher.",
        "expected_revision": 1,
    })
    assert updated.status_code == 200 and updated.json()["revision"] == 2
    history = client.get(drafts + "/" + draft["id"] + "/versions").json()
    assert [item["revision"] for item in history["items"]] == [2, 1]
    assert history["items"][1]["body"].endswith(f"[@{ref_id}].")
    assert client.put(drafts + "/" + draft["id"], headers=csrf(client), json={
        "title": "Stale", "body": "Would overwrite", "expected_revision": 1,
    }).status_code == 409
    assert client.post(drafts, headers=csrf(client), json={
        "title": "Bad marker", "body": "Unverified [@00000000-0000-0000-0000-000000000000]",
    }).status_code == 422
    assert client.post(drafts, headers=csrf(client), json={
        "title": "Malformed marker", "body": "Unverified [@oops]",
    }).status_code == 422
    assert client.post(drafts, headers=csrf(client), json={
        "title": "Malformed UUID", "body": "Unverified [@------------------------------------]",
    }).status_code == 422
    assert client.post(drafts + "/" + draft["id"] + "/remove", headers=csrf(client),
                       json={"expected_revision": 2}).status_code == 204
    assert client.get(drafts).json()["items"] == []


def test_drafts_are_private(client):
    project, _ = setup_source(client)
    drafts = f"/api/v1/projects/{project['id']}/drafts"
    created = client.post(drafts, headers=csrf(client), json={"title": "Private draft", "body": ""})
    assert created.status_code == 201
    draft_id = created.json()["id"]
    register(client, "writing-other@example.com")
    login(client, "writing-other@example.com")
    assert client.get(drafts).status_code == 404
    assert client.get(drafts + "/" + draft_id).status_code == 404
    assert client.get(drafts + "/" + draft_id + "/versions").status_code == 404
