"""Every structured table adapter must preserve labels and section context."""

from uuid import UUID

import pytest

from app.modules.documents.chunks import make_chunks, nearby_table_caption


@pytest.mark.parametrize(
    "detection",
    [
        "numbered-model-columns",
        "numbered-model-subcolumns",
        "aligned-labelled-columns",
        "aligned-numbered-section-columns",
        "continued-numbered-columns",
        "regression-model-columns",
    ],
)
def test_shared_table_chunk_contract(detection):
    counter = 0

    def cell(text):
        nonlocal counter
        counter += 1
        return {"id": str(counter), "text": text, "word_indices": []}

    table = {
        "detection": detection,
        "box": [0.1, 0.1, 0.9, 0.8],
        "rows": [
            [cell(""), cell("Use AI"), cell("Do not use AI")],
            [cell("A. Owner characteristics"), cell(""), cell("")],
            [cell("Advanced degree"), cell("31.5"), cell("21.9")],
            [cell("B. Startup financing"), cell(""), cell("")],
            [cell("Venture capital"), cell("2.9"), cell("0.8")],
        ],
    }
    layout = {"version": "contract-fixture", "passages": [], "tables": [table]}
    chunks = make_chunks(UUID(int=1), "a" * 64, [layout])
    assert len(chunks) == 2
    assert (
        chunks[0]["text"]
        == "A. Owner characteristics | Advanced degree | Use AI: 31.5 | Do not use AI: 21.9"
    )
    assert (
        chunks[1]["text"]
        == "B. Startup financing | Venture capital | Use AI: 2.9 | Do not use AI: 0.8"
    )
    assert chunks == make_chunks(UUID(int=1), "a" * 64, [layout])


def test_table_caption_is_associated_only_when_unique_and_nearby():
    layout = {
        "words": [
            {"text": "TABLE", "box": [0.1, 0.04, 0.18, 0.06]},
            {"text": "A3", "box": [0.19, 0.04, 0.23, 0.06]},
            {"text": "Rates", "box": [0.24, 0.04, 0.3, 0.06]},
        ],
        "passages": [
            {"id": "caption", "text": "TABLE A3 Rates", "word_indices": [0, 1, 2]}
        ],
    }
    table = {"box": [0.1, 0.08, 0.9, 0.8]}
    assert nearby_table_caption(layout, table) == layout["passages"][0]
    layout["passages"].append(
        {"id": "second", "text": "TABLE A4 Other rates", "word_indices": [0, 1, 2]}
    )
    assert nearby_table_caption(layout, table) is None
