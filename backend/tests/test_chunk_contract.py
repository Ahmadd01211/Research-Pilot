"""Every structured table adapter must preserve labels and section context."""

from uuid import UUID

import pytest

from app.modules.documents.chunks import make_chunks


@pytest.mark.parametrize(
    "detection",
    [
        "numbered-model-columns",
        "numbered-model-subcolumns",
        "aligned-labelled-columns",
        "aligned-numbered-section-columns",
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
    assert len(chunks) == 3
    assert (
        chunks[1]["text"]
        == "A. Owner characteristics | Advanced degree | Use AI: 31.5 | Do not use AI: 21.9"
    )
    assert (
        chunks[2]["text"]
        == "B. Startup financing | Venture capital | Use AI: 2.9 | Do not use AI: 0.8"
    )
    assert chunks == make_chunks(UUID(int=1), "a" * 64, [layout])
