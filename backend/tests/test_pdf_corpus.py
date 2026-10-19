"""Real parser checks across synthetic PDFs, not mocks of measured geometry."""

from hashlib import sha256
from io import BytesIO
from uuid import UUID

import pdfplumber
import pytest
from pypdf import PdfReader

from app.modules.documents.chunks import make_chunks
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
        assert len(rows) == 6
        assert all(
            len(row) == (4 if case == "model-table" else 3 if case == "two-model-table" else 2)
            for row in rows
        )
        assert not body & table
        if case == "model-table":
            assert rows[1][2]["text"] == ""
            assert (
                "(2) Revenue: [blank in source]"
                in [c for c in chunks if c["kind"] == "table_row"][1]["text"]
            )
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
            assert figure["box"] is None
            assert all(c["kind"] != "prose" for c in chunks)
            fallback.append("full-page visual; ordinary page prose withheld")
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
        "words": len(words),
        "tables": len(layout["tables"]),
        "figures": len(layout["figures"]),
        "chunks": len(chunks),
        "limitations": fallback,
    }


@pytest.mark.parametrize("case", CASES)
def test_real_pdf_corpus(case):
    check_case(case)
