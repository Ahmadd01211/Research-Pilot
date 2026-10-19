# Extraction regression corpus

The corpus generates twelve original synthetic PDFs and runs the real pdfplumber reader, schema validation and source chunker. It does not download papers, need API credentials, use the application database, or claim a universal accuracy score. The supplied 41-page research paper is a separate local acceptance sample, not committed to the repository.

| Family | Checked contract |
| --- | --- |
| Prose, crop, rotations 90/180/270 | Exact expected word sequence, valid normalized coordinates, bounded passage count on rotations |
| Two-column page | Both columns' tokens retained; general reading order remains uncertified |
| Shaded definition table | Six rows, two cells per row, no duplication into prose |
| Numbered model table | Six rows, four columns, blank model cells retained and headings included in row chunks |
| Embedded figure | Actual caption and measured image region |
| Vector figure | Explicit full-page fallback and ordinary page prose withheld from chunks |
| Uncaptioned image | Measured region without an invented caption |
| Equation with multiple baselines | Extracted coordinates/tokens preserved; semantic reconstruction remains uncertified |

Every case checks valid word boxes, valid source anchors, passage text matching its anchored words, no overlap between table/caption words and prose, repeatable chunk identities, and original checksum/page provenance. Earlier tests separately cover malformed/encrypted files, limits, ambiguous figures, private-use mathematical glyphs, ownership and transaction failure. Frontend tests cover switching image/caption/text/cell targets and excluding misplaced mathematical glyph boxes.

## Running the checks

From the repository root, the ordinary isolated backend test command includes every corpus case automatically:

```powershell
docker compose -f compose.test.yaml build tests
docker compose -f compose.test.yaml up --abort-on-container-exit --exit-code-from tests
docker compose -f compose.test.yaml down
```

For a standalone JSON report without a database, using the built backend image:

```powershell
docker run --rm --network none researchpilot-greenfield-backend:dev python -m scripts.check_extraction_corpus
```

The command exits nonzero on a failed contract. Use a newly built image when checking changes. `docs/extraction-quality-report.json` records this checkpoint, while the executable checks are authoritative for later changes. Existing CI runs pytest, so these cases join its normal regression gate. This is a development gate, not a per-upload quality classifier or evidence that embedding is safe for every document.

## What the corpus found

Valid coordinates alone masked fragmented words on rotated pages. Reader v8 selects the text-flow character direction from page rotation and measures paragraph gaps along the original reading axis. Exact-token and passage-count assertions now catch both failures. Static PDF.js renders were inspected with measured overlays for all three rotations; no browser screenshots were automated.

The supplied paper was parsed locally again. Physical page 8 retains one two-column table with ten rows; outside it are three body passages, a title and notes. Physical page 18 retains the seven-column, twenty-row regression table. Original files remain unchanged. Table cell highlight controls are separate verification anchors; retrieval uses whole rows rather than isolated cells.

## Limits and next additions

This synthetic set makes failures repeatable but is not representative of all publishers. We still need independently reviewed samples across publishers, scanned PDFs/OCR, multilingual and right-to-left text, borderless/merged-cell tables, multi-panel graphics, mixed text orientations and complex equations. These are not certified by a passing report. Keep conservative fallbacks and formula warnings; do not turn this report into a blanket RAG-ready badge. Before enabling embeddings, review representative real source chunks and evaluate known-answer retrieval and citation support. No external model calls or automatic reprocessing occur here.

Existing documents require Update readable text and highlights to use reader v8. Deferred conflict reconciliation and Trash/retention/purge remain unchanged.

## Two-model regression table correction — 19 October 2026
Reader v9 supports two sequential numbered model columns when a nearby table caption is present, while retaining measured empty-gutter and shaded-boundary validation. Half-point closing-rule tolerance handles contiguous shading/rule coordinate rounding without creating empty rows. Supplied paper physical page 20 / printed 394 now yields one three-column, thirteen-row table: both model headings remain in its header row; title, notes and body prose are separate. Page-8 ten-row and page-18 twenty-row tables remain intact. The original synthetic corpus now contains thirteen layouts, including a captioned two-model table, and checks caption/table separation. Existing uploads require the explicit reader upgrade; original/raw text unchanged.

