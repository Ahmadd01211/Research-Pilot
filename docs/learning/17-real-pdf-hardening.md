# 17 — Hardening extraction against real papers

24 November 2026. Synthetic PDFs cannot show which rules fail on real publisher output.
This slice ran the production path (`extract_with_layout` → `make_chunks`) on 25 public
papers: arXiv (CS, math, physics, statistics, q-bio, a 1997 hep-th paper), PLOS, ACL,
NeurIPS, JMLR and a NIST report. Six other downloads were HTML pages and were correctly
rejected as `invalid_pdf`.

## Bug 1 — a schema mismatch rejected whole documents (fixed)

`quality.py` reports figure problems with `scope="figure"`. `QualityFinding.scope` did not
allow `"figure"`. `extraction.py` validates every page's layout against `ReaderLayout`, and
a `ValidationError` was caught as `ValueError` and reported as `invalid_pdf`.

Result: one oversized or misaligned figure on any page made the whole paper fail as an
invalid PDF, and its readable text was discarded. 4 of the first 11 papers failed this way
(GAN, BERT, LoRA, Chain-of-Thought). Nothing was logged, and the message told users to
re-export a PDF that was fine.

Fixes:
- `schemas.py` allows `"figure"`.
- `tests/test_extraction_contract.py` parses `quality.py` and checks that every scope it
  emits is accepted by the schema, so the two cannot drift silently again.
- `parse_pdf.parse()` separates the stages. pypdf failures are still `invalid_pdf`.
  Exceptions in our layout heuristics become `layout_failure`, with a diagnostic of only
  the exception type and file:line (no message or source text).
- `extraction.checked_result()` reports violations of the reader's own contract as
  `layout_failure` and logs the document UUID and the failing field path. The UI says
  plainly that this is not a problem with the user's PDF, and offers a retry: the failure is
  deterministic, so it is never retried automatically, but the owner may request another
  attempt after an update (still capped at 5 attempts).
- Blame is by location. An exception whose innermost frame is inside pdfminer or
  pdfplumber, or a zero-area page box (`InvalidPageBox`), is the file's defect and stays
  `invalid_pdf`. Anything raised in our code is `layout_failure`.
- A word narrower than the 6-decimal box rounding used to pass the degenerate-box check
  before rounding and then fail the contract after it. Boxes are now rounded first.

## Bug 2 — readable paragraphs silently withheld from search (fixed)

A coverage probe measured the share of readable body words that become searchable chunks:
**88%** at the start. The largest causes were two over-broad rules.

1. **One undecodable symbol blocked a whole paragraph.** A single `(cid:18)` or a Symbol
   font private-use glyph (for example U+F061, α) inside a 150-word paragraph withheld it,
   which cost 18,472 words. Now `glyph_dense()` withholds a passage only when undecodable
   symbols exceed 1 per 20 tokens, which means it is really a formula. Sparse symbols
   become a visible `[?]` in search text only, and the page gets a
   `sparse_undecoded_symbols` warning. Original text, highlights and raw extraction are
   unchanged.
2. **An uncertain figure withheld all page prose.** Chart text (axis ticks, legends,
   letter-spaced labels) arrives as separate short passages with almost no function words.
   Real paragraphs are long and ordinary. Now only passages that fail `clear_prose()` are
   withheld: at least 25 tokens, at least 15% common function words, under 30%
   single-letter tokens, and under 15% numeric tokens. The numeric guard was added after
   review, so small flattened tables such as ResNet page 5 also stay withheld. Unmatched table captions and fragmented text still withhold all
   page prose, because there the risk is wrong numbers. See the ADR 0008 amendment.

Result on the same papers: **95.8%** searchable. VAE went from 44% to 82%, HNSW from 59% to 89%,
GAN from 62% to 89%. A leak audit listed all 93 newly kept chunks on figure-uncertain pages: all were
paragraphs except one small table flattened next to its caption (ResNet page 5), whose
numbers keep their original order and page link.

Still withheld, intentionally: dense numeric prose (flattened tables), formula-dense
passages, arXiv side stamps and unclassified front matter. Remaining loss is about 4%.

## Bug 3 — too little time headroom (fixed)

Profiling LoRA (26 pages, 22 s) showed about 97% of the time in pdfminer decoding the
vector paths of embedded plots (about 64,000 paths). Our heuristics are cheap. The CPU cap
was 40 s, so a longer figure-heavy paper would fail with `resource_limit`. The CPU cap is
now 90 s and the wall timeout 100 s. A test pins the order:
CPU < wall < Celery soft limit < hard limit < job lease. If that order breaks, a live worker
can be killed mid-publication or a job claimed twice.

## Versions and existing data

`READER_VERSION` is now `word-passages-v33`, `QUALITY_VERSION` `evidence-quality-v5` and
`CHUNKER_VERSION` `source-types-v13`. The three must move together. Chunks are rebuilt only
when the reader version changes (the explicit "Update readable text and highlights" action,
or the automatic refresh when indexing). A chunker-only bump would strand every existing
document, because search, matrix and gaps filter on the new chunker version. A code
review caught exactly that in this slice. `test_derived_version_bumps_travel_together`
now pins the combination. Existing documents show the reader-update notice; after updating
(and reindexing when embeddings are on), their new chunks are searchable.

The extraction task has its own Celery limits (160 s soft, 190 s hard), so publishing pages
and chunks has at least 45 s after a maximal parse, and stays under the 240 s job lease.

## Check your own papers

`backend/scripts/real_pdf_coverage.py` runs offline (`--network none`) on a local folder
and prints, per PDF, the outcome, time, chunks, searchable share and withheld words by
reason. It exits 1 if any PDF hits `layout_failure`. The usage line is in the script header.

## Limits

These are heuristics measured on 25 papers, not a guarantee for every PDF. The prose test
uses English function words, so non-English prose on figure-uncertain pages stays withheld
(as before this change). Scanned PDFs
still need OCR. Unusual layouts can still be withheld (lower recall) rather than guessed.
