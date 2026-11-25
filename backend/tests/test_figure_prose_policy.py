"""An uncertain figure withholds chart-like text, not the page's paragraphs."""

from uuid import uuid4

from app.modules.documents.chunks import make_chunks
from app.modules.documents.quality import assess_page

PARAGRAPH = (
    "The construction process can be easily parallelized because the insertion of each "
    "element only requires the search of its neighbors in the graph and the update of "
    "their connections which is a local operation in the structure of the index"
)
LABELS = "0,0 0,5 1,0 1,5 2,0 0,09 0,10 0,11"
SPACED = "Q u e r y t i m e , m s"


def page(*texts: str, figure_box=None, table_caption=False) -> dict:
    words, passages = [], []
    for n, text in enumerate(texts):
        start = len(words)
        for k, token in enumerate(text.split()):
            x = 0.05 + (k % 18) * 0.05
            y = 0.1 + n * 0.2 + (k // 18) * 0.02
            words.append({"text": token, "box": [x, y, x + 0.04, y + 0.015], "margin": False})
        passages.append(
            {"id": f"{n}" * 64, "text": text, "word_indices": list(range(start, len(words)))}
        )
    if table_caption:
        words += [
            {"text": "TABLE", "box": [0.05, 0.9, 0.1, 0.92], "margin": False},
            {"text": "3", "box": [0.11, 0.9, 0.12, 0.92], "margin": False},
        ]
    figures = [{
        "id": "f" * 64, "label": "Figure 6", "caption": "Fig. 6. Query time.",
        "caption_word_indices": [], "box": figure_box, "detection": "source_page",
        "related_passages": [],
    }]
    return {"version": "figure-prose-test", "words": words, "passages": passages,
            "tables": [], "figures": figures, "links": []}


def test_uncertain_figure_keeps_full_paragraphs_and_withholds_chart_labels():
    layout = page(PARAGRAPH, LABELS, SPACED)
    quality = assess_page(layout)
    assert not quality["withhold_prose"]
    assert quality["blocked_passage_ids"] == ["1" * 64, "2" * 64]
    prose = [c["source_id"] for c in make_chunks(uuid4(), "a" * 64, [layout]) if c["kind"] == "prose"]
    assert prose == ["0" * 64]


def test_flattened_small_table_on_uncertain_figure_page_stays_withheld():
    table = (
        "plain ResNet 18 layers 27.94 27.88 34 layers 28.54 25.03 Table 2. Top-1 error of the "
        "networks on the validation set and the results are shown in the table with the 10 crop"
    )
    layout = page(PARAGRAPH, table)
    assert assess_page(layout)["blocked_passage_ids"] == ["1" * 64]


def test_unmatched_table_caption_still_withholds_all_page_prose():
    layout = page(PARAGRAPH, table_caption=True)
    layout["figures"] = []
    assert assess_page(layout)["withhold_prose"]
    assert [c for c in make_chunks(uuid4(), "a" * 64, [layout]) if c["kind"] == "prose"] == []
