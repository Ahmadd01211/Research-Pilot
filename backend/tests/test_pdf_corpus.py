"""Real parser checks across synthetic PDFs, not mocks of measured geometry."""

from hashlib import sha256
from io import BytesIO
from uuid import UUID

import pdfplumber
import pytest
from pypdf import PdfReader

from app.modules.documents.chunks import make_chunks
from app.modules.documents.quality import assess_page
from app.modules.documents.reader import prepare_layouts
from app.modules.documents.schemas import ReaderLayout
from tests.pdf_corpus import CASES, corpus_pdf


def check_case(case):
    source = corpus_pdf(case)
    with pdfplumber.open(BytesIO(source)) as pdf:
        layouts = prepare_layouts(pdf)
    layout = ReaderLayout.model_validate(layouts[0]).model_dump(mode="json")
    words = layout["words"]
    assert words
    for word in words:
        a, b, c, d = word["box"]
        assert 0 <= a < c <= 1 and 0 <= b < d <= 1
    cells = [c for t in layout["tables"] for row in t["rows"] for c in row]
    for passage in layout["passages"] + cells:
        assert passage["text"] == " ".join(words[i]["text"] for i in passage["word_indices"])
        assert len(passage["id"]) == 64
    body = {i for p in layout["passages"] for i in p["word_indices"]}
    table = {i for c in cells for i in c["word_indices"]}
    captions = {i for f in layout["figures"] for i in f["caption_word_indices"]}
    assert not body & table and not body & captions
    chunks = make_chunks(UUID(int=1), sha256(source).hexdigest(), [layout])
    assert chunks == make_chunks(UUID(int=1), sha256(source).hexdigest(), [layout])
    for chunk in chunks:
        assert chunk["source_sha256"] == sha256(source).hexdigest() and chunk["page_number"] == 1
    fallback = []
    if case.endswith("table"):
        assert len(layout["tables"]) == 1
        rows = layout["tables"][0]["rows"]
        assert len(rows) == (
            3
            if case in {"continued-numeric-table", "continued-categorical-table"}
            else 5
            if case == "regression-multiheader-table"
            else 7
            if case == "summary-table"
            else 6
        )
        assert all(
            len(row)
            == (
                6
                if case == "summary-table"
                else 5
                if case == "grouped-table"
                else 5
                if case == "continued-numeric-table"
                else 8
                if case == "continued-categorical-table"
                else 5
                if case == "regression-multiheader-table"
                else 3
                if case == "ambiguous-grouped-table"
                else 4
                if case == "model-table"
                else 3
                if case == "two-model-table"
                else 2
            )
            for row in rows
        )
        assert not body & table
        if case == "model-table":
            assert rows[1][2]["text"] == ""
            assert (
                "(2) Revenue: [blank in source]"
                in [c for c in chunks if c["kind"] == "table_row"][1]["text"]
            )
    if case == "numbered-section-numeric":
        assert len(layout["tables"]) == 1
        rows = layout["tables"][0]["rows"]
        assert len(rows) == 9 and all(len(row) == 5 for row in rows)
        assert rows[0][3]["text"] == "(3) Do not use AI"
        assert rows[2][0]["text"] == "Characteristic 1"
        assert rows[2][4]["text"] == "1.4"
        assert rows[5][0]["text"] == "B. Startup financing"
        assert not body & table
        assert any("Notes:" in p["text"] for p in layout["passages"])
        assert any("Do not use AI: 1.3" in c["text"] for c in chunks)
    if case == "back-matter":
        roles = [p.get("role", "body") for p in layout["passages"]]
        assert roles == [
            "body", "acknowledgments", "data_availability", "orcid",
            "endnotes", "endnotes", "endnotes", "references", "body",
        ]
        note_text = [p["text"] for p in layout["passages"] if p.get("role") == "endnotes"]
        assert note_text[1].startswith("1 The first note")
        assert note_text[2].startswith("2 The second note")
        eligible = [c["text"] for c in chunks if c["kind"] == "prose"]
        assert len(eligible) == 5
        assert all(not any(word in c for word in ("Colleagues", "ORCID", "REFERENCES", "ENDNOTES")) for c in eligible)
        assert any("Approved researchers" in c for c in eligible)
        assert any("another measured result" in c for c in eligible)
    if case == "continued-numeric-table":
        assert layout["tables"][0]["detection"] == "continued-numbered-columns"
        assert layout["tables"][0]["rows"][0][2]["text"] == "(2) Use AI"
        quality = assess_page(layout)
        assert not quality["withhold_prose"]
        assert "unstructured_table" not in {finding["code"] for finding in quality["findings"]}
        rows = [c for c in chunks if c["kind"] == "table_row"]
        assert len(rows) == 2
        assert "Use AI: 17.1" in rows[0]["text"]
        assert "Difference: -0.7" in rows[0]["text"]
        assert not any("Continuation notes" in c["text"] for c in rows)
    if case == "continued-categorical-table":
        table = layout["tables"][0]
        assert table["detection"] == "continued-numbered-columns"
        assert table["rows"][0][0]["text"] == "Description"
        assert [cell["text"] for cell in table["rows"][1][1:]] == ["Yes"] * 7
        assert table["rows"][2][7]["text"] == "209,000"
        assert not any("Notes:" in cell["text"] for row in table["rows"] for cell in row)
        assert "unstructured_table" not in {finding["code"] for finding in assess_page(layout)["findings"]}
        assert len([chunk for chunk in chunks if chunk["kind"] == "table_row"]) == 2
    if case == "regression-multiheader-table":
        table = layout["tables"][0]
        assert table["detection"] == "regression-model-columns"
        assert not any(
            "publisher" in cell["text"].lower()
            for row in table["rows"]
            for cell in row
        )
        assert [cell["text"] for cell in table["rows"][0]] == [
            "Outcome",
            "(1) All firms",
            "(2) AI users",
            "(3) NonAI users",
            "(4) Difference overall",
        ]
        rows = [chunk for chunk in chunks if chunk["kind"] == "table_row"]
        assert len(rows) == 4
        assert "0.11*** (0.02)" in rows[0]["text"]
        assert "Advanced degree (1/0)" in rows[1]["text"]
        assert "(3) NonAI users: 0.01 (0.02)" in rows[2]["text"]
        quality = assess_page(layout)
        assert not quality["withhold_prose"]
        assert "unstructured_table" not in {finding["code"] for finding in quality["findings"]}
    if case == "front-matter":
        roles = {p["role"] for p in layout["passages"]}
        assert {
            "publication_metadata",
            "title",
            "authors",
            "affiliations",
            "correspondence",
            "funding",
            "abstract",
            "body",
        } <= roles
        abstract = next(p for p in layout["passages"] if p["role"] == "abstract")
        assert "survey evidence" in abstract["text"] and "University" not in abstract["text"]
        assert (
            next(p for p in layout["passages"] if p["role"] == "title")["text"]
            == "Evidence in academic systems"
        )
        assigned = [i for p in layout["passages"] for i in p["word_indices"]]
        assert len(assigned) == len(set(assigned))
        assert any(c["source_metadata"]["evidence_role"] == "abstract" for c in chunks)
        assert all(
            not any(
                term in c["text"]
                for term in [
                    "10.0000",
                    "Alice Example",
                    "University",
                    "author@example.com",
                    "foundation",
                ]
            )
            for c in chunks
        )
    if case == "front-matter-unanchored":
        assert all(p["role"] == "body" for p in layout["passages"])
        fallback.append("missing body anchor; front-matter classification not inferred")
    if case == "section-heading":
        heading = next(p for p in layout["passages"] if "3.3" in p["text"])
        assert heading["text"].startswith("3.3 | Early use and adoption")
        assert "preceding discussion" not in heading["text"]
        assert any(p["text"].startswith("The preceding discussion") for p in layout["passages"])
        assert any(c["text"].startswith("3.3 | Early use and adoption") for c in chunks)
    if case == "decimal-prose":
        assert len(layout["passages"]) == 1
        assert "3.3 percent" in layout["passages"][0]["text"]
    if case == "summary-table":
        assert [c["text"] for c in rows[1]] == [
            "Employment (unweighted)",
            "1.1",
            "1.2",
            "1.3",
            "1.4",
            "1.5",
        ]
        assert [c["text"] for c in rows[0][1:]] == [f"({n}) Sample Group{n}" for n in range(1, 6)]
        assert any("(5) Sample Group5: 1.5" in c["text"] for c in chunks)
        assert not any(
            "preceding paragraph" in p["text"] and "TABLE" in p["text"] for p in layout["passages"]
        )
        assert not any("TABLE" in p["text"] and "Notes:" in p["text"] for p in layout["passages"])
        assert any(p["text"].startswith("Notes:") for p in layout["passages"])
    if case in {"sectioned-numeric", "ambiguous-sectioned-numeric"}:
        assert len(layout["tables"]) == 1
        rows = layout["tables"][0]["rows"]
        assert len(rows) == 9 and all(len(row) == 4 for row in rows)
        assert [c["text"] for c in rows[0]] == [
            "",
            "Usage rate (%) Yes",
            "Usage rate (%) No",
            "Usage rate (%) Difference",
        ]
        if case == "sectioned-numeric":
            assert [c["text"] for c in rows[2]] == ["Characteristic 1", "8.4", "5.3", "3.1"]
            assert any(
                "A. Owner characteristics | Characteristic 1 | Usage rate (%) Yes: 8.4" in c["text"]
                and "Difference: 3.1" in c["text"]
                for c in chunks
            )
            assert any("B. Startup conditions | Condition 1" in c["text"] for c in chunks)
            assert len([c for c in chunks if c["kind"] == "table_row"]) == 6
        else:
            assert layout["tables"][0]["detection"] == "aligned-labelled-ambiguous"
            assert not any(c["kind"] == "table_row" for c in chunks)
            fallback.append("uncertain numeric alignment; table withheld from retrieval")
        assert not any("Notes:" in c["text"] for row in rows for c in row)
    if case == "grouped-table":
        assert layout["tables"][0]["detection"] == "numbered-model-subcolumns"
        assert [cell["text"] for cell in rows[0]] == [
            "Location",
            "(1) Firm-weighted Share",
            "(1) Firm-weighted Rank",
            "(2) Employment-weighted Share",
            "(2) Employment-weighted Rank",
        ]
        assert [cell["text"] for cell in rows[1]] == ["City 1", "1.4", "11", "1.8", "21"]
        assert rows[2][2]["text"] == ""
        body_ids = [i for row in rows[1:] for cell in row for i in cell["word_indices"]]
        assert len(body_ids) == len(set(body_ids))
        assert any(
            "(1) Firm-weighted Share: 1.4" in c["text"]
            and "(2) Employment-weighted Rank: 21" in c["text"]
            for c in chunks
        )
    if case == "ambiguous-grouped-table":
        assert layout["tables"][0]["detection"] == "numbered-model-columns-ambiguous"
        assert not any(c["kind"] == "table_row" for c in chunks)
        fallback.append("crossing subcolumn gutter; table withheld from retrieval")
    if case == "two-model-table":
        assert rows[0][1]["text"] == "(1) Revenue"
        assert rows[0][2]["text"] == "(2) Revenue"
        assert rows[1][2]["text"] == "0.14 (0.05)"
        caption_words = {
            i for p in layout["passages"] for i in p["word_indices"] if words[i]["text"] == "TABLE"
        }
        assert caption_words and not caption_words & table
    if case in {"vector-figure", "image-figure", "uncaptioned-image"}:
        assert len(layout["figures"]) == 1
        figure = layout["figures"][0]
        if case == "vector-figure":
            assert figure["box"] is not None
            assert figure["detection"] == "vector_graphics"
            assert all(
                "Synthetic measured results" not in c["text"]
                for c in chunks
                if c["kind"] == "prose"
            )
            fallback.append("measured vector diagram crop; ordinary page prose withheld")
        else:
            assert figure["box"] is not None
        if case == "uncaptioned-image":
            assert figure["caption"] is None
        else:
            assert figure["caption"] == "FIGURE 1 Synthetic measured results."
    if case in {"prose", "crop", "rotation-90", "rotation-180", "rotation-270"}:
        assert (
            [w["text"] for w in words]
            == "Alpha evidence supports the first independently measured result. Beta evidence describes a separate result with source attribution.".split()
        )
    if case.startswith("rotation-"):
        assert len(layout["passages"]) <= 2
    if case == "two-columns":
        assert "Alpha" in " ".join(w["text"] for w in words) and "Beta" in " ".join(
            w["text"] for w in words
        )
        fallback.append("token preservation checked; general column reading order is not certified")
    if case == "equation-baselines":
        assert "(1)" in " ".join(w["text"] for w in words)
        fallback.append("coordinate/token preservation only; mathematical semantics not certified")
    raw = PdfReader(BytesIO(source)).pages[0].extract_text()
    assert raw
    return {
        "case": case,
        "assessment": layout["quality"]["state"],
        "quality_findings": [finding["code"] for finding in layout["quality"]["findings"]],
        "links": len(layout["links"]),
        "words": len(words),
        "tables": len(layout["tables"]),
        "figures": len(layout["figures"]),
        "chunks": len(chunks),
        "limitations": fallback,
    }


@pytest.mark.parametrize("case", CASES)
def test_real_pdf_corpus(case):
    check_case(case)
