"""One undecodable math symbol must not hide an otherwise readable paragraph."""

from uuid import uuid4

from app.modules.documents.chunks import make_chunks
from app.modules.documents.quality import assess_page

PROSE = (
    "We assume that the prior and likelihood come from parametric families of distributions "
    "and that their probability density functions are differentiable almost everywhere with "
    "respect to both the parameters and the latent variables used in this model"
)


def layout(text: str) -> dict:
    tokens = text.split()
    words = [
        {"text": t, "box": [0.05 + (n % 20) * 0.045, 0.1 + (n // 20) * 0.03,
                            0.09 + (n % 20) * 0.045, 0.12 + (n // 20) * 0.03], "margin": False}
        for n, t in enumerate(tokens)
    ]
    return {
        "version": "glyph-test",
        "words": words,
        "passages": [{"id": "p" * 64, "text": text, "word_indices": list(range(len(words)))}],
        "tables": [],
        "figures": [],
        "links": [],
    }


def test_sparse_cid_glyph_keeps_paragraph_searchable_with_visible_marker():
    page = layout(PROSE.replace("prior", "prior p (cid:18) θ"))
    quality = assess_page(page)
    assert quality["blocked_passage_ids"] == []
    assert any(
        f["code"] == "sparse_undecoded_symbols" and f["severity"] == "warning"
        for f in quality["findings"]
    )
    [chunk] = make_chunks(uuid4(), "a" * 64, [page])
    assert "(cid:18)" not in chunk["text"] and "[?]" in chunk["text"]
    assert chunk["source_id"] == "p" * 64


def test_sparse_private_use_glyph_keeps_paragraph_searchable():
    page = layout(PROSE.replace("latent", "latent "))
    assert assess_page(page)["blocked_passage_ids"] == []
    [chunk] = make_chunks(uuid4(), "a" * 64, [page])
    assert "" not in chunk["text"] and "[?]" in chunk["text"]


def test_formula_dense_passage_remains_withheld():
    page = layout("L ( θ , φ ; x ) = (cid:2) (cid:3)  E q  log p ( x | z )")
    quality = assess_page(page)
    assert quality["blocked_passage_ids"] == ["p" * 64]
    assert make_chunks(uuid4(), "a" * 64, [page]) == []
