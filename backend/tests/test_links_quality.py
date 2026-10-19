from hashlib import sha256
from io import BytesIO
from uuid import uuid4

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, FloatObject, NameObject, TextStringObject

from app.modules.documents.chunks import make_chunks
from app.modules.documents.extraction import extract_with_layout
from app.modules.documents.links import safe_target
from app.modules.documents.models import DocumentPageText
from app.modules.documents.processing import run_document
from app.modules.documents.quality import assess_page
from tests.conftest import csrf, login, register
from tests.pdf_fixture import pdf_bytes
from tests.test_processing import setup


def linked_pdf(rotation=0, crop=False):
    writer = PdfWriter()
    writer.append(
        PdfReader(
            BytesIO(
                pdf_bytes(
                    [
                        "Read the linked research evidence and dataset for this study.",
                        "The source identifier is 10.1234/example and remains page-linked.",
                    ]
                )
            )
        )
    )

    def add(action):
        writer.add_annotation(
            0,
            DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Annot"),
                    NameObject("/Subtype"): NameObject("/Link"),
                    NameObject("/Rect"): ArrayObject([FloatObject(n) for n in [70, 710, 430, 740]]),
                    NameObject("/A"): action,
                }
            ),
        )

    add(
        DictionaryObject(
            {
                NameObject("/S"): NameObject("/URI"),
                NameObject("/URI"): TextStringObject("https://example.org/dataset?source=paper"),
            }
        )
    )
    add(
        DictionaryObject(
            {
                NameObject("/S"): NameObject("/GoTo"),
                NameObject("/D"): ArrayObject(
                    [writer.pages[1].indirect_reference, NameObject("/Fit")]
                ),
            }
        )
    )
    add(
        DictionaryObject(
            {
                NameObject("/S"): NameObject("/JavaScript"),
                NameObject("/JS"): TextStringObject("app.alert('never execute')"),
            }
        )
    )
    add(
        DictionaryObject(
            {
                NameObject("/S"): NameObject("/GoToR"),
                NameObject("/F"): TextStringObject("remote.pdf"),
                NameObject("/D"): ArrayObject([FloatObject(0), NameObject("/Fit")]),
            }
        )
    )
    writer.add_named_destination("source-section", 1)
    add(
        DictionaryObject(
            {
                NameObject("/S"): NameObject("/GoTo"),
                NameObject("/D"): TextStringObject("source-section"),
            }
        )
    )
    add(
        DictionaryObject(
            {
                NameObject("/S"): NameObject("/GoTo"),
                NameObject("/D"): TextStringObject("missing-section"),
            }
        )
    )
    if rotation:
        writer.pages[0].rotate(rotation)
    if crop:
        writer.pages[0].cropbox.lower_left = (40, 40)
        writer.pages[0].cropbox.upper_right = (570, 760)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


@pytest.mark.parametrize(
    "value",
    [
        "javascript:alert(1)",
        "file:///secret",
        "data:text/html,test",
        "https://user:pass@example.org",
        "https://example.org:bad",
        "https://example.org/\nsecret",
        "mailto:person@example.org?body=test",
        "https://",
        None,
    ],
)
def test_unsafe_destinations_are_not_navigable(value):
    assert safe_target(value) is None


def test_links_survive_real_bounded_extraction_and_attach_to_chunk_metadata(tmp_path):
    original = linked_pdf()
    path = tmp_path / "links.pdf"
    path.write_bytes(original)
    pages, layouts, error = extract_with_layout(path, sha256(original).hexdigest())
    assert error is None
    links = layouts[0]["links"]
    assert any(
        link["target"] == "https://example.org/dataset?source=paper" and link["source_ids"]
        for link in links
    )
    assert sum(link["status"] == "internal" and link["target_page"] == 2 for link in links) == 2
    assert any(link["status"] == "unresolved" for link in links)
    assert sum(link["status"] == "blocked" and link["target"] is None for link in links) == 2
    assert any(
        link["origin"] == "visible_doi" and link["target"] == "https://doi.org/10.1234/example"
        for link in layouts[1]["links"]
    )
    assert layouts[0]["quality"]["state"] == "needs_review"
    chunks = make_chunks(uuid4(), sha256(original).hexdigest(), layouts)
    assert any(
        any(
            link["target"] == "https://example.org/dataset?source=paper"
            for link in c["source_metadata"]["links"]
        )
        for c in chunks
    )
    assert all("https://example.org/dataset" not in c["text"] for c in chunks)
    assert path.read_bytes() == original and pages


def layout(text="A measured source statement."):
    words = [
        {"text": t, "box": [0.1 + n * 0.1, 0.2, 0.18 + n * 0.1, 0.22], "margin": False}
        for n, t in enumerate(text.split())
    ]
    return {
        "version": "quality-test",
        "words": words,
        "passages": [{"id": "a" * 64, "text": text, "word_indices": list(range(len(words)))}],
        "tables": [],
        "figures": [],
        "links": [],
    }


def test_quality_blocks_invalid_anchors_not_reading_or_originals():
    page = layout()
    page["passages"][0]["word_indices"] = [999]
    assert assess_page(page)["block_page"]
    assert make_chunks(uuid4(), "a" * 64, [page]) == []


def test_unknown_table_caption_automatically_withholds_page_prose():
    page = layout("TABLE 9 Unknown layout.")
    quality = assess_page(page)
    assert quality["withhold_prose"] and any(
        f["code"] == "unstructured_table" for f in quality["findings"]
    )
    assert make_chunks(uuid4(), "a" * 64, [page]) == []


def test_quality_blocks_undecodable_passage_without_discarding_good_passage():
    page = layout()
    page["words"].append({"text": "\uf0da", "box": [0.1, 0.4, 0.2, 0.42], "margin": False})
    page["passages"].append(
        {"id": "b" * 64, "text": "\uf0da", "word_indices": [len(page["words"]) - 1]}
    )
    assert assess_page(page)["blocked_passage_ids"] == ["b" * 64]
    assert [c["source_id"] for c in make_chunks(uuid4(), "a" * 64, [page])] == ["a" * 64]


def test_quality_report_is_owned_current_and_marks_legacy_as_unassessed(client):
    project, document, factory, storage = setup(client)
    run_document(factory, storage, document)
    path = f"/api/v1/projects/{project}/documents/{document}/quality"
    report = client.get(path)
    assert report.status_code == 200
    assert report.json()["checked_pages"] == 2
    with factory() as db:
        row = db.get(DocumentPageText, (document, 1))
        row.layout = {**row.layout, "version": "older-reader"}
        db.commit()
    assert client.get(path).json()["not_assessed_pages"] == 1
    register(client, "quality-outsider@example.com")
    login(client, "quality-outsider@example.com")
    assert client.get(path).status_code == 404
    login(client)
    client.request(
        "DELETE", f"/api/v1/projects/{project}", headers=csrf(client), json={"expected_revision": 1}
    )
    assert client.get(path).status_code == 404


def test_bad_table_shape_cannot_break_or_contaminate_good_prose():
    page = layout()
    cell = {"id": "cell", "text": page["words"][0]["text"], "word_indices": [0]}
    page["tables"] = [
        {
            "box": [0.1, 0.1, 0.9, 0.8],
            "detection": "numbered-model-columns",
            "rows": [[cell, cell], [cell]],
        }
    ]
    assert assess_page(page)["blocked_table_indices"] == [0]
    chunks = make_chunks(uuid4(), "a" * 64, [page])
    assert len(chunks) == 1 and chunks[0]["kind"] == "prose"


def test_empty_or_fragmented_pages_do_not_become_retrieval_evidence():
    empty = {"version": "test", "words": [], "passages": [], "tables": [], "figures": []}
    assert assess_page(empty)["state"] == "blocked"
    page = layout()
    page["words"] = [
        {
            "text": "x",
            "box": [
                0.05 + (i % 10) * 0.08,
                0.1 + (i // 10) * 0.05,
                0.08 + (i % 10) * 0.08,
                0.12 + (i // 10) * 0.05,
            ],
            "margin": False,
        }
        for i in range(40)
    ]
    page["passages"] = [
        {"id": "a" * 64, "text": " ".join("x" for _ in range(40)), "word_indices": list(range(40))}
    ]
    assert assess_page(page)["withhold_prose"]
    assert make_chunks(uuid4(), "a" * 64, [page]) == []


def test_link_count_is_bounded_and_simple_mailto_is_supported():
    from app.modules.documents.links import page_links

    class Page:
        bbox = (0, 0, 100, 100)
        annots = [{}] * 501

    with pytest.raises(MemoryError):
        page_links(Page(), [], {}, 1)
    assert safe_target("mailto:author@example.com") == "mailto:author@example.com"


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_link_locations_follow_crop_and_rotation(tmp_path, rotation):
    original = linked_pdf(rotation=rotation, crop=True)
    path = tmp_path / "rotated-links.pdf"
    path.write_bytes(original)
    _, layouts, error = extract_with_layout(path, sha256(original).hexdigest())
    assert error is None
    link = next(
        link
        for link in layouts[0]["links"]
        if link["target"] == "https://example.org/dataset?source=paper"
    )
    assert link["word_indices"] and link["source_ids"]
    a, b, c, d = link["box"]
    assert 0 <= a < c <= 1 and 0 <= b < d <= 1
