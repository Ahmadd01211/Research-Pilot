"""Our own reader/quality output must never be reported as the user's invalid PDF."""

import ast
import inspect
from typing import get_args

import pytest

from app.modules.documents import parse_pdf, quality
from app.modules.documents.extraction import checked_result
from app.modules.documents.quality import assess_page
from app.modules.documents.schemas import QualityFinding, ReaderLayout
from tests.pdf_fixture import pdf_bytes


def page(**extra):
    words = [{"text": f"w{i}", "box": [0.1, 0.02 * i, 0.2, 0.02 * i + 0.01], "margin": False}
             for i in range(1, 30)]
    layout = {
        "version": "test",
        "width": 600.0,
        "height": 800.0,
        "rotation": 0,
        "words": words,
        "passages": [],
        "excluded_margin_text": [],
    }
    layout.update(extra)
    return layout


def test_oversized_figure_finding_validates_as_a_reader_layout():
    # Regression: arXiv 1406.2661/1810.04805/2106.09685/2201.11903 were rejected
    # as invalid PDFs because figure-scoped findings failed schema validation.
    layout = page(
        figures=[{
            "id": "f1", "label": "Figure 1", "caption": None, "caption_word_indices": [],
            "box": [0.02, 0.02, 0.98, 0.9], "detection": "embedded_image", "related_passages": [],
        }]
    )
    layout["quality"] = assess_page(layout)
    assert any(f["scope"] == "figure" for f in layout["quality"]["findings"])
    ReaderLayout.model_validate(layout)


def test_every_quality_scope_is_accepted_by_the_schema():
    allowed = set(get_args(QualityFinding.model_fields["scope"].annotation))
    tree = ast.parse(inspect.getsource(quality))
    used = {
        call.args[3].value
        for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        and getattr(call.func, "id", None) == "issue"
        and len(call.args) == 4
        and isinstance(call.args[3], ast.Constant)
    }
    assert used, "expected quality.issue(...) calls"
    assert used <= allowed


def test_layout_contract_violation_is_reported_as_layout_failure_not_invalid_pdf():
    bad = page()
    bad["passages"] = [{"id": "p1", "text": "x", "word_indices": [0], "role": "not-a-role"}]
    pages, layouts, error = checked_result({"pages": ["Some readable text " * 5], "layouts": [bad]})
    assert (pages, layouts, error) == (None, None, "layout_failure")


def test_layout_heuristic_crash_is_reported_as_layout_failure(tmp_path, monkeypatch):
    path = tmp_path / "ok.pdf"
    path.write_bytes(pdf_bytes(["A readable research sentence that is long enough."]))

    def crash(_pdf):
        raise IndexError("heuristic bug")

    monkeypatch.setattr("app.modules.documents.reader.prepare_layouts", crash)
    result = parse_pdf.parse(str(path))
    assert result["error"] == "layout_failure"
    assert result["diagnostic"]["type"] == "IndexError"
    assert result["diagnostic"]["where"].startswith("test_extraction_contract.py:")
    assert "heuristic bug" not in str(result)  # Diagnostics never carry messages/source text.


def test_derived_version_bumps_travel_together():
    """Chunks are rebuilt only when READER_VERSION changes (prepare-reader / auto refresh).

    Bumping the chunker or quality version alone strands every existing document:
    search, matrix and gaps filter on the new chunker version, but nothing can rebuild.
    When this fails, bump READER_VERSION too, then update the pinned tuple.
    """
    from app.modules.documents.chunks import CHUNKER_VERSION
    from app.modules.documents.quality import QUALITY_VERSION
    from app.modules.documents.reader import READER_VERSION

    pinned = {
        ("source-types-v14", "evidence-quality-v5"): "word-passages-v34",
    }
    assert pinned.get((CHUNKER_VERSION, QUALITY_VERSION)) == READER_VERSION.split(":")[0]


def test_parser_time_budgets_nest_inside_worker_and_lease_limits():
    from app.modules.documents.extraction import PARSER_WALL_SECONDS
    from app.modules.documents.processing import LEASE_SECONDS
    from app.workers.celery_app import celery_app
    from app.workers.document_tasks import extract_document  # noqa: F401  (registers task)

    task = celery_app.tasks["researchpilot.documents.extract"]
    soft, hard = task.soft_time_limit, task.time_limit
    # CPU < wall: the CPU cap fires first with an honest resource_limit.
    # wall + margin < soft: publishing pages and chunks after a slow parse can commit.
    # hard < lease: a live worker is never treated as abandoned and duplicated.
    assert parse_pdf.CPU_SECONDS < PARSER_WALL_SECONDS < soft < hard < LEASE_SECONDS
    assert soft - PARSER_WALL_SECONDS >= 45
    # Figure-heavy real papers used 22s of CPU; keep at least 3x headroom.
    assert parse_pdf.CPU_SECONDS >= 66


def test_pdf_library_errors_after_pypdf_are_not_called_our_bug(tmp_path, monkeypatch):
    path = tmp_path / "ok.pdf"
    path.write_bytes(pdf_bytes(["A readable research sentence that is long enough."]))

    def fails_inside_pdfminer(_pdf):
        from pdfminer.psparser import PSBaseParser

        PSBaseParser(None).nexttoken()  # no stream: raises from pdfminer's own frame

    monkeypatch.setattr("app.modules.documents.reader.prepare_layouts", fails_inside_pdfminer)
    result = parse_pdf.parse(str(path))
    assert result["error"] == "invalid_pdf"
    assert result["diagnostic"]["where"].startswith("psparser.py:")


def test_zero_area_page_box_is_the_pdfs_defect(tmp_path, monkeypatch):
    from app.modules.documents.reader import InvalidPageBox

    path = tmp_path / "ok.pdf"
    path.write_bytes(pdf_bytes(["A readable research sentence that is long enough."]))

    def bad_box(_pdf):
        raise InvalidPageBox("Invalid page box")

    monkeypatch.setattr("app.modules.documents.reader.prepare_layouts", bad_box)
    assert parse_pdf.parse(str(path))["error"] == "invalid_pdf"


def test_word_narrower_than_rounding_is_dropped_not_fatal():
    from app.modules.documents.extraction import checked_result
    from app.modules.documents.reader import prepare_layouts

    class Page:
        bbox = cropbox = (0, 0, 100, 100)
        rotation = 0
        rects = lines = curves = images = []

        def crop(self, *args, **kwargs):
            return self

        def close(self):
            pass

        def extract_words(self, **kwargs):
            sentence = [
                {"text": f"word{i}", "x0": 5 + i * 4, "x1": 8 + i * 4, "top": 10, "bottom": 12}
                for i in range(20)
            ]
            # An invisible text-layer glyph 1e-7 points wide: distinct before rounding only.
            return sentence + [{"text": "x", "x0": 50.0, "x1": 50.0000001, "top": 30, "bottom": 32}]

    class PDF:
        pages = [Page()]

    layouts = prepare_layouts(PDF())
    assert "x" not in [w["text"] for w in layouts[0]["words"]]
    pages, checked, error = checked_result({"pages": ["text " * 20], "layouts": layouts})
    assert error is None and checked is not None


def test_layout_failure_can_be_retried_by_the_owner_after_a_fix(client):
    from app.modules.documents.processing import locked_job
    from tests.conftest import csrf
    from tests.test_processing import setup

    project, document, factory, _storage = setup(client)
    with factory() as db:
        job = locked_job(db, document)
        assert job is not None
        job.state, job.error_code, job.attempts = "failed", "layout_failure", 1
        db.commit()
    response = client.post(
        f"/api/v1/projects/{project}/documents/{document}/retry", headers=csrf(client)
    )
    assert response.status_code == 200, response.text
    assert response.json()["processing"]["state"] == "queued"


@pytest.mark.parametrize("payload", [b"%PDF-1.4\nbroken"])
def test_unreadable_pdf_structure_is_still_invalid_pdf(tmp_path, payload):
    path = tmp_path / "bad.pdf"
    path.write_bytes(payload)
    assert parse_pdf.parse(str(path))["error"] == "invalid_pdf"
