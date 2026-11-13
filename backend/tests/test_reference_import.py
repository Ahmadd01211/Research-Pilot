"""BibTeX/RIS import parses to reviewable drafts and saves only researcher-confirmed records."""

from uuid import uuid4

import pytest

from app.modules.references.importing import (
    MAX_IMPORT_ENTRIES,
    ImportSyntaxError,
    latex_text,
    parse_bibtex,
    parse_ris,
)
from tests.conftest import csrf, login, register
from tests.test_projects import authenticated, create

BIBTEX = r"""
% Exported from a reference manager
@string{jrp = "Journal of Research " # "Practice"}
@comment{ignored {nested} text}
@article{lovelace2024,
  author  = {Ada Lovelace and Ludwig van Beethoven and M{\"u}ller, J{\"o}rg and {World Health Organization}},
  title   = {{AI} Adoption in {\'E}cole Systems: 10\% Gains --- Revisited},
  journal = jrp,
  year    = 2024,
  doi     = {https://doi.org/10.1234/ABC\_def},
  url     = {https://example.org/paper?id=1\&x=2},
}
@inproceedings(conf1,
  author = "Smith, Jane and others",
  title = "A \textit{Conference} Paper with \unknowncommand",
  booktitle = {Proceedings of Things},
  date = {2021-06-01}
)
@misc{arxiv1, author={Chen, Li}, title={Preprint}, archivePrefix={arXiv}, year={1200}}
"""

RIS = """﻿TY  - JOUR
ID  - ris-1
AU  - Scholar, Ada
AU  - Doe, John
TI  - A long title that
  continues on the next line
T2  - Journal of Studies
PY  - 2023/05/01/
DO  - doi:10.5555/XYZ
UR  - https://a.example/one
UR  - https://b.example/two
ER  -

TY  - CHAP
TI  - Chapter
A2  - Editor, Ed
BT  - Big Book
PY  - n.d.
ER  -
"""


def test_bibtex_parser_cleans_latex_names_macros_and_kinds():
    first, second, third = parse_bibtex(BIBTEX)
    assert first.label == "lovelace2024" and first.kind == "journal"
    assert first.title == "AI Adoption in École Systems: 10% Gains — Revisited"
    assert first.authors == ["Lovelace, Ada", "van Beethoven, Ludwig", "Müller, Jörg",
                             "World Health Organization"]
    assert first.container_title == "Journal of Research Practice" and first.year == 2024
    assert first.doi == "https://doi.org/10.1234/ABC_def"
    assert first.url == "https://example.org/paper?id=1&x=2"
    assert second.kind == "conference" and second.year == 2021
    assert second.title == "A Conference Paper with \\unknowncommand"
    assert second.authors == ["Smith, Jane"]
    assert any("others" in item for item in second.warnings)
    assert any("\\unknowncommand" in item for item in second.warnings)
    assert third.kind == "preprint" and third.year is None
    assert any("outside 1500" in item for item in third.warnings)


def test_ris_parser_handles_continuations_multiple_urls_and_chapters():
    article, chapter = parse_ris(RIS)
    assert article.label == "ris-1" and article.kind == "journal"
    assert article.title == "A long title that continues on the next line"
    assert article.authors == ["Scholar, Ada", "Doe, John"]
    assert (article.year, article.container_title, article.doi) == (2023, "Journal of Studies", "doi:10.5555/XYZ")
    assert article.url == "https://a.example/one" and any("2 URLs" in item for item in article.warnings)
    assert chapter.kind == "other" and chapter.authors == [] and chapter.container_title == "Big Book"
    assert any("editors" in item for item in chapter.warnings)
    assert any("chapter" in item for item in chapter.warnings)


@pytest.mark.parametrize("text, message", [
    ("@article{a, title = {unclosed", "not closed"),
    ("@article{a, title = {x}}}", None),
    ("@article{a title = {x}}", "expected"),
    ("TY  - JOUR\nTI  - x\n", "no ER"),
    ("TY  - JOUR\nTY  - BOOK\nER  -\n", "before ER"),
])
def test_malformed_files_fail_with_location(text, message):
    parser = parse_ris if text.startswith("TY") else parse_bibtex
    if message is None:
        assert len(parser(text)) == 1  # Trailing text outside an entry is a BibTeX comment.
        return
    with pytest.raises(ImportSyntaxError, match=message):
        parser(text)


def test_entry_limit_and_latex_escapes_are_bounded():
    with pytest.raises(ImportSyntaxError, match=str(MAX_IMPORT_ENTRIES)):
        parse_bibtex("@misc{x, title={t}}\n" * (MAX_IMPORT_ENTRIES + 1))
    assert latex_text(r"Na\"{\i}ve \{set\} \c{c}a \ss", [], "x") == "Naïve {set} ça ß"


def _project(client):
    authenticated(client)
    project = create(client)
    return f"/api/v1/projects/{project['id']}/references", project


def test_preview_flags_duplicates_and_import_is_idempotent(client):
    base, _ = _project(client)
    existing = client.post(base, headers=csrf(client), json={
        "kind": "journal", "title": "Already Saved", "authors": ["Scholar, Ada"], "year": 2020,
        "container_title": "", "doi": "10.9999/saved", "url": "", "document_id": None,
    })
    assert existing.status_code == 201, existing.text
    text = r"""
@article{dup, author={Scholar, Ada}, title={Already saved}, year={2020}, doi={10.9999/SAVED}}
@article{probable, author={Scholar, Ada}, title={Already Saved!}, year=2020}
@article{good, author={Ada Lovelace}, title={Fresh Study}, year=2022, doi={10.1000/x}}
@article{again, author={Ada Lovelace}, title={Fresh copy}, year=2022, doi={10.1000/X}}
@article{bad, title={No authors}, doi={not-a-doi}, url={ftp://x}}
"""
    preview = client.post(base + "/import/preview", headers=csrf(client),
                          json={"format": "bibtex", "text": text})
    assert preview.status_code == 200, preview.text
    body = preview.json()
    items = {item["label"]: item for item in body["items"]}
    assert body["remaining_capacity"] == 499
    assert not items["dup"]["importable"] and items["dup"]["duplicate_of"] == existing.json()["id"]
    assert items["probable"]["importable"] and items["probable"]["duplicate_of"] == existing.json()["id"]
    assert items["good"]["importable"] and items["good"]["authors"] == ["Lovelace, Ada"]
    assert items["good"]["doi"] == "10.1000/x"
    assert not items["again"]["importable"] and "earlier in this file" in items["again"]["errors"][0]
    assert not items["bad"]["importable"] and items["bad"]["doi"] is None and items["bad"]["url"] == ""
    assert len(client.get(base).json()["items"]) == 1  # Preview never saves.

    good = items["good"]
    record = {key: good[key] for key in ("kind", "title", "authors", "year", "container_title", "doi", "url")}
    payload = {"request_id": str(uuid4()), "items": [record, {**record, "title": "Second", "doi": None}]}
    created = client.post(base + "/import", headers=csrf(client), json=payload)
    assert created.status_code == 201, created.text
    ids = [item["id"] for item in created.json()["items"]]
    assert len(ids) == 2
    replay = client.post(base + "/import", headers=csrf(client), json=payload)
    assert replay.status_code == 201 and [item["id"] for item in replay.json()["items"]] == ids
    assert len(client.get(base).json()["items"]) == 3
    changed = client.post(base + "/import", headers=csrf(client),
                          json={**payload, "items": [{**record, "title": "Other", "doi": None}]})
    assert changed.status_code == 409


def test_import_is_atomic_scoped_and_blocked_when_archived(client):
    base, project = _project(client)
    record = {"kind": "journal", "title": "Valid", "authors": ["Scholar, Ada"], "year": 2021,
              "container_title": "", "doi": "10.2000/a", "url": "", "document_id": None}
    failed = client.post(base + "/import", headers=csrf(client), json={
        "request_id": str(uuid4()),
        "items": [record, {**record, "title": "Bad link", "doi": None, "url": "javascript:x"}],
    })
    assert failed.status_code == 422 and failed.json()["detail"].startswith("Item 2:")
    duplicate = client.post(base + "/import", headers=csrf(client), json={
        "request_id": str(uuid4()), "items": [record, {**record, "title": "Same DOI"}],
    })
    assert duplicate.status_code == 409
    assert client.get(base).json()["items"] == []
    malformed = client.post(base + "/import/preview", headers=csrf(client),
                            json={"format": "ris", "text": "TY  - JOUR\nTI  - x\n"})
    assert malformed.status_code == 422 and "ER" in malformed.json()["detail"]
    empty = client.post(base + "/import/preview", headers=csrf(client),
                        json={"format": "bibtex", "text": "just prose"})
    assert empty.status_code == 422

    project_path = f"/api/v1/projects/{project['id']}"
    archived = client.post(project_path + "/archive", headers=csrf(client),
                           json={"expected_revision": project["revision"]})
    assert archived.status_code == 200, archived.text
    assert client.post(base + "/import", headers=csrf(client), json={
        "request_id": str(uuid4()), "items": [record],
    }).status_code == 409

    register(client, "import-other@example.com")
    login(client, "import-other@example.com")
    assert client.post(base + "/import/preview", headers=csrf(client),
                       json={"format": "bibtex", "text": "@misc{a, title={t}}"}).status_code == 404
    assert client.post(base + "/import", headers=csrf(client), json={
        "request_id": str(uuid4()), "items": [record],
    }).status_code == 404
