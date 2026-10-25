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


def test_reference_import_preview_parses_bibtex_without_writing_records(client):
    project, _ = setup_source(client)
    base = f"/api/v1/projects/{project['id']}/references"
    bibtex = """@article{smith2024,
      title = {A {Careful} Study of AI},
      author = {Smith, Jane and {World Health Organization} and {{Research and Development Board}}},
      journal = {Journal of Research}, year = 2024,
      volume = {12}, number = {2}, pages = {10--20},
      doi = {10.1234/example}, url = {https://example.org/paper}
    }"""
    response = client.post(base + "/import/preview", headers=csrf(client),
                           json={"format": "bibtex", "content": bibtex})
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["preview_only"] is True
    assert len(preview["items"]) == 1
    item = preview["items"][0]
    assert item["title"] == "A Careful Study of AI"
    assert item["authors"] == ["Smith, Jane", "World Health Organization", "Research and Development Board"]
    assert item["kind"] == "journal" and item["year"] == 2024
    assert item["pages"] == "10--20" and item["doi"] == "10.1234/example"
    assert client.get(base).json()["items"] == []

    macro = client.post(base + "/import/preview", headers=csrf(client),
                        json={"format": "bibtex", "content": "@article{x, title={Macro}, author={Scholar, A}, journal=JournalMacro}"})
    assert macro.status_code == 200
    assert macro.json()["items"][0]["container_title"] == ""
    assert any("string macro" in warning for warning in macro.json()["items"][0]["warnings"])


def test_reference_import_preview_parses_ris_and_enforces_limits(client):
    project, _ = setup_source(client)
    base = f"/api/v1/projects/{project['id']}/references"
    ris = """TY  - JOUR
TI  - A RIS study
AU  - Scholar, Alex
PY  - 2023/02/01
JF  - Journal of Tests
SP  - 5
EP  - 9
DO  - 10.1234/ris
ER  -
"""
    response = client.post(base + "/import/preview", headers=csrf(client),
                           json={"format": "ris", "content": ris})
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["kind"] == "journal" and item["year"] == 2023
    assert item["authors"] == ["Scholar, Alex"]
    assert item["pages"] == "5-9" and item["doi"] == "10.1234/ris"
    assert client.post(base + "/import/preview", headers=csrf(client),
                       json={"format": "ris", "content": "x" * 100_001}).status_code == 422
    assert client.post(base + "/import/preview", headers=csrf(client),
                       json={"format": "unknown", "content": "x"}).status_code == 422


def test_reference_import_preview_is_project_owner_scoped(client):
    project, _ = setup_source(client)
    base = f"/api/v1/projects/{project['id']}/references/import/preview"
    register(client, "reference-import-other@example.com")
    login(client, "reference-import-other@example.com")
    response = client.post(base, headers=csrf(client),
                           json={"format": "ris", "content": "TY  - JOUR\nER  -"})
    assert response.status_code == 404
