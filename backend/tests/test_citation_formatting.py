"""Bibliography previews use only stored fields, flag gaps, and stay owner-scoped and read-only."""

from app.modules.references.formatting import Source, format_source, parse_name
from tests.conftest import csrf, login, register
from tests.test_projects import authenticated, create

ARTICLE = Source("journal", "An AI adoption study", ["Scholar, Ada Marie", "Lee, Kim"], 2024,
                 "Journal of Studies", "10.1234/example", "")
REPORT = Source("book", "Global report", ["World Health Organization"], None, "", None,
                "https://who.example/report")


def italic(entry) -> list[str]:
    return [text for text, slanted in entry.segments if slanted]


def test_apa7_journal_book_conference_and_preprint():
    article = format_source(ARTICLE, "apa7")
    assert article.text == ("Scholar, A. M., & Lee, K. (2024). An AI adoption study. "
                            "Journal of Studies. https://doi.org/10.1234/example")
    assert italic(article) == ["Journal of Studies"] and article.warnings == []
    report = format_source(REPORT, "apa7")
    assert report.text == "World Health Organization. (n.d.). Global report. https://who.example/report"
    assert italic(report) == ["Global report"]
    paper = format_source(Source("conference", "Fast tools", ["Kahn, Ru"], 2022,
                                 "Proceedings of Tools", None, ""), "apa7")
    assert paper.text == "Kahn, R. (2022). Fast tools. In Proceedings of Tools."
    preprint = format_source(Source("preprint", "Testing ideas?", ["Ng, Jean-Paul"], 2023,
                                    "arXiv", None, ""), "apa7")
    assert preprint.text == "Ng, J.-P. (2023). Testing ideas? [Preprint]. arXiv."
    assert italic(preprint) == ["Testing ideas?"]


def test_mla9_entries_and_author_rules():
    article = format_source(ARTICLE, "mla9")
    assert article.text == ("Scholar, Ada Marie, and Kim Lee. “An AI adoption study.” "
                            "Journal of Studies, 2024, https://doi.org/10.1234/example.")
    report = format_source(REPORT, "mla9")
    assert report.text == "World Health Organization. Global report. https://who.example/report."
    assert "Year is missing, so no date is shown." in report.warnings
    three = format_source(Source("journal", "T", ["Ábel, Ana", "Bo, B", "Cy, C"], 2020, "J"), "mla9")
    assert three.text.startswith("Ábel, Ana, et al. “T.” J, 2020.")


def test_chicago18_bibliography_entries_and_long_author_lists():
    article = format_source(ARTICLE, "chicago18")
    assert article.text == ("Scholar, Ada Marie, and Kim Lee. “An AI adoption study.” "
                            "Journal of Studies (2024). https://doi.org/10.1234/example.")
    assert format_source(REPORT, "chicago18").text == (
        "World Health Organization. Global report. n.d. https://who.example/report.")
    seven = [f"Author{n}, Given{n}" for n in range(1, 8)]
    long = format_source(Source("book", "Big", seven, 2021, url="https://x.example"), "chicago18")
    assert long.text.startswith("Author1, Given1, Given2 Author2, Given3 Author3, et al. Big. 2021.")
    six = format_source(Source("book", "Six", seven[:6], 2021), "chicago18")
    assert "Given5 Author5, and Given6 Author6. Six. 2021." in six.text


def test_author_convention_is_preserved_without_guessing():
    assert parse_name("Scholar, Ada") == (parse_name("Scholar, Ada")[0], None)
    assert parse_name("Scholar,  Ada")[0].given == "Ada"
    organization, warning = parse_name("World Health Organization")
    assert organization.family is None and organization.raw == "World Health Organization"
    assert warning and "no comma" in warning
    _, suffix = parse_name("Smith, John, Jr.")
    assert suffix and "more than one comma" in suffix
    ambiguous = format_source(Source("journal", "Paper", ["A. Scholar"], 2024, "J", "10.1/x"), "apa7")
    assert ambiguous.text.startswith("A. Scholar. (2024).")
    assert any("“A. Scholar”" in w or "\"A. Scholar\"" in w for w in ambiguous.warnings)


def test_missing_metadata_is_warned_not_invented():
    bare = format_source(Source("journal", "Untitled draft", ["Øyelaran, Zoë"], None, ""), "apa7")
    assert bare.text == "Øyelaran, Z. (n.d.). Untitled draft."
    assert {"Journal is missing, so it is omitted.",
            "No DOI or URL is stored, so no link is shown.",
            "Year is missing; shown as “n.d.”."} <= set(bare.warnings)
    chapter = format_source(Source("book", "Book", ["Li, Na"], 2020, "Edited volume"), "mla9")
    assert "Edited volume" not in chapter.text
    assert any("book chapters are not supported" in w for w in chapter.warnings)


def test_bibliography_endpoint_orders_excludes_removed_and_is_read_only(client):
    authenticated(client)
    project = create(client)
    base = f"/api/v1/projects/{project['id']}/references"

    def add(title: str, authors: list[str], year: int | None) -> dict:
        response = client.post(base, headers=csrf(client), json={
            "kind": "journal", "title": title, "authors": authors, "year": year,
            "container_title": "J", "doi": None, "url": "", "document_id": None})
        assert response.status_code == 201, response.text
        return response.json()

    add("Zeta study", ["Bauer, Ben"], 2024)
    first = add("Alpha study", ["Ábel, Ana"], 2021)
    add("Same year", ["Bauer, Ben"], 2024)
    removed = add("Removed study", ["Aaron, Al"], 2020)
    assert client.post(f"{base}/{removed['id']}/remove", headers=csrf(client),
                       json={"expected_revision": 1}).status_code == 204

    response = client.get(base + "/bibliography")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["style"] == "apa7" and body["preview"] is True
    assert any("Limited preview" in item for item in body["limitations"])
    assert [item["text"].split(". (")[0] for item in body["items"]] == ["Ábel, A", "Bauer, B", "Bauer, B"]
    assert body["items"][0]["reference_id"] == first["id"]
    assert [item["text"].split(" (2024). ")[-1][:4] for item in body["items"][1:]] == ["Same", "Zeta"]
    assert all(any("letter suffixes" in w for w in item["warnings"]) for item in body["items"][1:])
    assert removed["id"] not in {item["reference_id"] for item in body["items"]}
    assert client.get(base + "/bibliography").json() == body
    assert client.get(base + "/settings").json()["revision"] == 0

    assert client.put(base + "/settings", headers=csrf(client),
                      json={"style": "chicago18", "expected_revision": 0}).status_code == 200
    chicago = client.get(base + "/bibliography").json()
    assert chicago["style"] == "chicago18"
    assert chicago["items"][0]["text"] == "Ábel, Ana. “Alpha study.” J (2021)."

    register(client, "bibliography-other@example.com")
    login(client, "bibliography-other@example.com")
    assert client.get(base + "/bibliography").status_code == 404
