from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.modules.documents.chunks import make_chunks
from app.modules.documents.models import EvidenceChunk
from app.modules.documents.processing import claim, finish, run_document
from app.modules.documents.reader import prepare_layouts
from tests.conftest import csrf, login, register
from tests.test_processing import setup


class FigurePage:
    bbox = (0, 0, 100, 100)
    cropbox = bbox
    rotation = 0
    rects = []
    images = [
        {"x0": 10, "top": 10, "x1": 90, "bottom": 40},
        {"x0": 1, "top": 1, "x1": 5, "bottom": 3},
    ]

    def crop(self, *args, **kwargs):
        return self

    def close(self):
        pass

    def extract_words(self, **kwargs):
        return [
            {"text": "Legend", "x0": 15, "x1": 35, "top": 20, "bottom": 24},
            {"text": "99%", "x0": 40, "x1": 50, "top": 20, "bottom": 24},
            {"text": "FIGURE", "x0": 10, "x1": 26, "top": 45, "bottom": 49},
            {"text": "1", "x0": 28, "x1": 32, "top": 45, "bottom": 49},
            {"text": "Survey results.", "x0": 35, "x1": 80, "top": 45, "bottom": 49},
            {
                "text": "Figure 1 is discussed by the authors in this source paragraph.",
                "x0": 10,
                "x1": 90,
                "top": 70,
                "bottom": 74,
            },
        ]


def fixture():
    class PDF:
        pages = [FigurePage()]

    return prepare_layouts(PDF())


def test_caption_crop_raw_labels_and_explicit_discussion():
    layouts = fixture()
    layout = layouts[0]
    assert len(layout["figures"]) == 1  # small logo is excluded
    figure = layout["figures"][0]
    assert figure["label"] == "Figure 1"
    assert figure["box"] == [0.1, 0.1, 0.9, 0.4]
    assert figure["caption"] == "FIGURE 1 Survey results."
    assert "discussed by the authors" in figure["related_passages"][0]["text"]
    assert "99%" not in " ".join(p["text"] for p in layout["passages"])
    assert "99%" in " ".join(w["text"] for w in layout["words"])  # raw/source words retained


def test_vector_or_ambiguous_graph_uses_full_page_and_does_not_invent_values():
    class Vector(FigurePage):
        images = []

    class PDF:
        pages = [Vector()]

    layout = prepare_layouts(PDF())[0]
    figure = layout["figures"][0]
    assert figure["box"] is None and figure["detection"] == "source_page"
    chunks = make_chunks(uuid4(), "a" * 64, [layout])
    assert {c["kind"] for c in chunks} == {"figure_caption"}
    assert all("99%" not in c["text"] for c in chunks)


def test_caption_above_embedded_figure_gets_a_focused_crop():
    class CaptionAbove(FigurePage):
        images = [{"x0": 10, "top": 50, "x1": 90, "bottom": 80}]

        def extract_words(self, **kwargs):
            return [
                {"text": "FIGURE", "x0": 10, "x1": 26, "top": 40, "bottom": 44},
                {"text": "1", "x0": 28, "x1": 32, "top": 40, "bottom": 44},
                {"text": "Survey results.", "x0": 35, "x1": 80, "top": 40, "bottom": 44},
            ]

    class PDF:
        pages = [CaptionAbove()]

    figures = prepare_layouts(PDF())[0]["figures"]
    assert len(figures) == 1
    assert figures[0]["box"] == [0.1, 0.5, 0.9, 0.8]
    assert figures[0]["detection"] == "embedded_image"


def test_uncaptioned_image_has_neutral_label_and_no_semantic_chunk():
    class Image(FigurePage):
        def extract_words(self, **kwargs):
            return []

    class PDF:
        pages = [Image()]

    layout = prepare_layouts(PDF())[0]
    figure = layout["figures"][0]
    assert figure["caption"] is None
    assert figure["label"] == "Visual evidence on PDF page 1"
    assert not make_chunks(uuid4(), "a" * 64, [layout])


def test_source_typed_chunk_identity_and_no_vision_claims():
    layouts = fixture()
    document = uuid4()
    first = make_chunks(document, "a" * 64, layouts)
    assert first == make_chunks(document, "a" * 64, layouts)
    assert {c["kind"] for c in first} == {"prose", "figure_caption"}
    assert all(c["source_sha256"] == "a" * 64 and c["page_number"] == 1 for c in first)
    assert (
        next(c for c in first if c["kind"] == "figure_caption")["source_metadata"][
            "image_interpretation"
        ]
        is False
    )
    changed = deepcopy(layouts)
    changed[0]["version"] = "another-reader"
    assert {c["id"] for c in first}.isdisjoint(
        {c["id"] for c in make_chunks(document, "a" * 64, changed)}
    )


def test_chunks_publish_atomically_and_prior_versions_survive(client):
    _, d, factory, storage = setup(client)
    run_document(factory, storage, d)
    with factory() as db:
        before = db.scalar(select(func.count()).select_from(EvidenceChunk))
        assert before > 0
    run_document(factory, storage, d)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(EvidenceChunk)) == before
    # Atomic failure must not add new chunk versions or expose a partial page set.
    from app.modules.documents.models import DocumentJob

    with factory() as db:
        db.get(DocumentJob, d).state = "queued"
        db.commit()
    token = claim(factory, d)[0]
    with patch(
        "app.modules.documents.processing.projects.record", side_effect=RuntimeError("synthetic")
    ):
        with pytest.raises(RuntimeError):
            finish(factory, d, token, ["raw"], None, fixture())
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(EvidenceChunk)) == before


def test_figure_endpoint_scope_and_real_publication(client):
    p, d, factory, _ = setup(client)
    token = claim(factory, d)[0]
    finish(factory, d, token, ["Original raw text remains here."], None, fixture())
    path = f"/api/v1/projects/{p}/documents/{d}/figures"
    result = client.get(path)
    assert result.status_code == 200, result.text
    figure = result.json()["items"][0]
    assert (
        figure["page_number"] == 1
        and figure["label"] == "Figure 1"
        and len(figure["source_sha256"]) == 64
    )
    register(client, "figure-outsider@example.com")
    login(client, "figure-outsider@example.com")
    assert client.get(path).status_code == 404
    login(client)
    client.request(
        "DELETE", f"/api/v1/projects/{p}", headers=csrf(client), json={"expected_revision": 1}
    )
    assert client.get(path).status_code == 404


def test_table_chunks_keep_cells_together_and_distinct_from_prose():
    layout = {
        "version": "reader-v5",
        "passages": [],
        "figures": [],
        "tables": [
            {
                "box": [0.1, 0.1, 0.9, 0.8],
                "rows": [
                    [
                        {"id": "a", "text": "Technology"},
                        {"id": "b", "text": "Definition from source"},
                    ]
                ],
            }
        ],
    }
    chunk = make_chunks(uuid4(), "b" * 64, [layout])[0]
    assert chunk["kind"] == "table_row"
    assert chunk["text"] == "Technology | Definition from source"
    assert chunk["source_metadata"]["cell_ids"] == ["a", "b"]


class TwoColumnView:
    """A US-letter page in normalised coordinates with a narrow (3.7%) column gutter."""

    bbox = (0, 0, 612, 792)
    images: list[dict[str, float]] = []


def two_column_words(right_lines: dict[int, str]) -> list[dict[str, object]]:
    words: list[dict[str, object]] = []
    for row in range(40):
        top = 0.1 + row * 0.015  # ~12 pt leading, as in body text
        for left, right, default in ((0.08, 0.468, "left column body text here now"),
                                     (0.505, 0.891, "right column body text here now")):
            if left < 0.5 and row in right_lines:
                continue  # paragraph break in the left column, as on the real page
            text = right_lines.get(row, default) if left > 0.5 else default
            tokens = text.split()
            step = (right - left) / len(tokens)
            for n, token in enumerate(tokens):
                words.append({"text": token, "box": [left + n * step, top,
                                                    left + (n + 1) * step - 0.004, top + 0.011]})
    return words


def test_caption_lines_never_cross_a_narrow_column_gutter():
    # ResNet p5: a right-column sentence starting "Fig. 4." absorbed the left column's
    # lines at the same height, interleaving both columns into one "caption" chunk.
    from app.modules.documents.figures import figures_on_page

    words = two_column_words({9: "an earlier sentence ends here.",
                              10: "Fig. 4. First the situation is reversed"})
    figures = figures_on_page(TwoColumnView(), words, [])
    caption_words = [words[i] for f in figures for i in f["caption_word_indices"]]
    assert caption_words, "the caption-like line should still be found"
    assert all(word["box"][0] > 0.49 for word in caption_words)


def test_a_sentence_continuing_onto_fig_n_is_not_a_caption():
    # ResNet p5: "...three major observations from Table 2 and" / "Fig. 4. First, ...".
    # Treating it as a caption swallowed the rest of the column's body text.
    from app.modules.documents.figures import figures_on_page

    words = two_column_words({9: "three major observations from Table 2 and",
                              10: "Fig. 4. First the situation is reversed"})
    assert figures_on_page(TwoColumnView(), words, []) == []


def test_figure_labels_above_a_real_caption_do_not_suppress_it():
    # ResNet: "F relu" (diagram labels) and axis ticks sit just above real captions.
    from app.modules.documents.figures import figures_on_page

    words = two_column_words({10: "Figure 2. Residual learning a building block."})
    words = [w for w in words if not (w["box"][0] > 0.5 and 0.1 + 9 * 0.015 <= w["box"][1] < 0.1 + 10 * 0.015)]
    words += [{"text": "F", "box": [0.62, 0.1 + 9 * 0.015, 0.63, 0.1 + 9 * 0.015 + 0.011]},
              {"text": "relu", "box": [0.70, 0.1 + 9 * 0.015, 0.73, 0.1 + 9 * 0.015 + 0.011]}]
    figures = figures_on_page(TwoColumnView(), words, [])
    assert [f["label"] for f in figures] == ["Figure 2"]
