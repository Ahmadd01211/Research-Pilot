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


The corpus now contains fifteen layouts, adding grouped parent/leaf table headers and an ambiguous crossing-gutter case. Checks assert exact labelled values, retained blank subcells, no body-word duplication and withholding uncertain table rows from retrieval.


## Unnumbered sectioned numeric tables — 19 October 2026
Reader v11 adds caption-validated, shaded-header unnumbered numeric tables with aligned leaf headings and measured source boxes. The supplied paper physical page 34 / printed 408 yields 38 rows and four columns: row label plus AI usage rate (%) Yes, No and Difference. Full-sample 6.0 remains outside the comparison rows. Section labels and quoted subsections remain source rows; chunker source-types-v5 carries their context into each data row and skips section-only chunks. Uncertain numeric alignment is marked and its table rows withheld from retrieval. This supports a conservative single-line numeric-table family, not arbitrary unnumbered or multiline tables. Existing uploads need an explicit reader update; originals/raw text unchanged. The synthetic corpus adds sectioned-numeric and ambiguous-sectioned-numeric cases (17 layouts total).


## Partial-shading summary table — 19 October 2026
Reader v12 collects partial-width row shading inside a full-width header/closing-rule boundary, while retaining gutter validation. The supplied paper physical page 7 now yields six columns and seven rows, preserving all five numbered sample headings and six data rows; Employment (unweighted) remains distinct from Employment (weighted), as do age and observations. Paragraph-to-caption boundaries are explicit for uppercase TABLE plus an identifier, and Notes/Note starts; skipping measured table/figure regions flushes prior prose so captions do not join subsequent notes. Raw bytes/text remain unchanged. Existing uploads require an explicit reader update. Eighteen synthetic layouts now include a partial-shading summary table with wrapped row labels, separate prose/title/notes and labelled row chunks. All 72 isolated backend tests, Ruff and strict mypy pass; prior source tables on pages 8/18/20/33/34 remain detected. Frontend source unchanged in this slice.

