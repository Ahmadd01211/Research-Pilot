from hashlib import sha256
from io import BytesIO

from pypdf import PdfReader, PdfWriter

from app.modules.documents.extraction import extract_with_layout
from app.modules.documents.models import DocumentPageText
from app.modules.documents.processing import run_document
from tests.conftest import csrf, login, register
from tests.pdf_fixture import pdf_bytes
from tests.test_processing import setup


def test_readable_passages_preserve_raw_and_measured_boxes(client):
    p, d, factory, storage = setup(client)
    original = storage.path(d).read_bytes()
    run_document(factory, storage, d)
    page = client.get(f"/api/v1/projects/{p}/documents/{d}/pages/1").json()
    assert page["text"] == PdfReader(BytesIO(original)).pages[0].extract_text().strip()
    layout = page["layout"]
    assert layout["width"] == 612 and layout["height"] == 792
    assert layout["passages"][0]["text"].startswith("This academic paper")
    for word in layout["words"]:
        x0, y0, x1, y1 = word["box"]
        assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1
    assert len(layout["passages"][0]["id"]) == 64
    for passage in layout["passages"]:
        assert passage["text"] == " ".join(
            layout["words"][i]["text"] for i in passage["word_indices"]
        )
    assert storage.path(d).read_bytes() == original


def test_existing_raw_extraction_requires_explicit_owned_preparation(client):
    p, d, factory, storage = setup(client)
    run_document(factory, storage, d)
    path = f"/api/v1/projects/{p}/documents/{d}"
    with factory() as db:
        for n in [1, 2]:
            db.get(DocumentPageText, (d, n)).layout = None
        db.commit()
    assert client.post(path + "/prepare-reader").status_code == 403
    register(client, "reader-outsider@example.com")
    login(client, "reader-outsider@example.com")
    assert client.post(path + "/prepare-reader", headers=csrf(client)).status_code == 404
    login(client)
    response = client.post(path + "/prepare-reader", headers=csrf(client))
    assert response.status_code == 200 and response.json()["status"] == "queued"
    assert client.post(path + "/prepare-reader", headers=csrf(client)).status_code == 409
    run_document(factory, storage, d)
    assert client.get(path + "/pages/1").json()["layout"] is not None
    assert client.post(path + "/prepare-reader", headers=csrf(client)).status_code == 409


def test_crop_and_rotation_boxes_use_the_rendered_page(client):
    for rotation in [0, 90, 180, 270]:
        reader = PdfReader(BytesIO(pdf_bytes()))
        writer = PdfWriter()
        page = reader.pages[0]
        page.cropbox.lower_left = (40, 40)
        page.cropbox.upper_right = (570, 770)
        page.rotate(rotation)
        writer.add_page(page)
        out = BytesIO()
        writer.write(out)
        temporary = client.app.state.settings.storage_root.parent / f"crop-{rotation}.pdf"
        temporary.write_bytes(out.getvalue())
        texts, layouts, error = extract_with_layout(temporary, sha256(out.getvalue()).hexdigest())
        assert error is None, (rotation, error)
        layout = layouts[0]
        expected = (530, 730) if rotation in [0, 180] else (730, 530)
        assert (layout["width"], layout["height"]) == expected
        assert layout["words"]


def test_repeated_margin_cleanup_never_changes_raw_or_numbers(client):
    from app.modules.documents.reader import prepare_layouts

    # A deterministic geometry fixture isolates cleanup rules from PDF text encodings.
    class Page:
        cropbox = (0, 0, 100, 100)
        bbox = cropbox
        rotation = 0

        def crop(self, *args, **kwargs):
            return self

        def close(self):
            pass

        def extract_words(self, **kwargs):
            return [
                {"text": "Running header 2024", "x0": 10, "x1": 80, "top": 1, "bottom": 3},
                {"text": "18.5%", "x0": 10, "x1": 25, "top": 20, "bottom": 23},
                {"text": "AI-related", "x0": 27, "x1": 60, "top": 20, "bottom": 23},
            ]

    class PDF:
        pages = [Page(), Page(), Page()]

    layouts = prepare_layouts(PDF())
    for page in layouts:
        assert page["excluded_margin_text"] == ["Running header 2024"]
        assert page["passages"][0]["text"] == "18.5% AI-related"
        assert len(page["words"]) == 3
    assert layouts[0]["passages"][0]["id"] != layouts[1]["passages"][0]["id"]
