"""Reference metadata stays researcher-controlled, scoped, and conflict-safe."""

from tests.conftest import csrf, login, register
from tests.test_matrix import setup_source


def test_reference_lifecycle_duplicates_and_style(client):
    project, document_id = setup_source(client)
    base = f"/api/v1/projects/{project['id']}/references"
    payload = {"kind": "journal", "title": "An AI Adoption Study", "authors": ["A. Scholar"],
               "year": 2024, "container_title": "Journal of Studies",
               "doi": "https://doi.org/10.1234/EXAMPLE", "url": "", "document_id": document_id}
    created = client.post(base, headers=csrf(client), json=payload)
    assert created.status_code == 201, created.text
    record = created.json()
    assert record["doi"] == "10.1234/example" and record["document_id"] == document_id
    assert client.post(base, headers=csrf(client), json={**payload, "doi": "doi:10.1234/example"}).status_code == 409
    match = client.get(base + "/duplicates", params={"title": "an ai-adoption study", "year": 2024})
    assert [item["id"] for item in match.json()["items"]] == [record["id"]]
    assert client.get(base + "/settings").json()["style"] == "apa7"
    style = client.put(base + "/settings", headers=csrf(client), json={"style": "chicago18", "expected_revision": 0})
    assert style.status_code == 200 and style.json()["revision"] == 1
    assert client.put(base + "/settings", headers=csrf(client), json={"style": "mla9", "expected_revision": 0}).status_code == 409
    revised = client.put(base + "/" + record["id"], headers=csrf(client), json={**payload, "title": "Revised Study", "expected_revision": 1})
    assert revised.status_code == 200 and revised.json()["revision"] == 2
    assert client.put(base + "/" + record["id"], headers=csrf(client), json={**payload, "expected_revision": 1}).status_code == 409
    assert client.post(base + "/" + record["id"] + "/remove", headers=csrf(client), json={"expected_revision": 2}).status_code == 204
    assert client.get(base).json()["items"] == []


def test_references_are_owner_scoped_and_archived_projects_are_read_only(client):
    project, document_id = setup_source(client)
    base = f"/api/v1/projects/{project['id']}/references"
    payload = {"kind": "journal", "title": "Source paper", "authors": ["A. Scholar"],
               "year": 2023, "container_title": "", "doi": None, "url": "", "document_id": document_id}
    assert client.post(base, headers=csrf(client), json=payload).status_code == 201
    register(client, "reference-other@example.com")
    login(client, "reference-other@example.com")
    assert client.get(base).status_code == 404
    assert client.get(base + "/settings").status_code == 404
    assert client.post(base, headers=csrf(client), json=payload).status_code == 404

def test_reference_publication_details_roundtrip_and_legacy_update(client):
    project, _ = setup_source(client)
    base = f"/api/v1/projects/{project['id']}/references"
    payload = {"kind": "journal", "title": "Detailed study", "authors": ["Scholar, Ada"],
               "year": 2024, "container_title": "Journal", "volume": "12", "issue": "3",
               "pages": "45-67", "article_number": "", "publisher": "Publisher", "edition": "2nd ed."}
    created = client.post(base, headers=csrf(client), json=payload)
    assert created.status_code == 201, created.text
    item = created.json()
    for key in ("volume", "issue", "pages", "article_number", "publisher", "edition"):
        assert item[key] == payload[key]
    legacy = {key: value for key, value in payload.items() if key not in
              ("volume", "issue", "pages", "article_number", "publisher", "edition")}
    updated = client.put(base + "/" + item["id"], headers=csrf(client),
                         json={**legacy, "title": "Edited by old client", "expected_revision": 1})
    assert updated.status_code == 200
    assert updated.json()["volume"] == "12" and updated.json()["pages"] == "45-67"
    clear = client.put(base + "/" + item["id"], headers=csrf(client),
                       json={**legacy, "volume": "", "expected_revision": 2})
    assert clear.status_code == 200 and clear.json()["volume"] == ""
