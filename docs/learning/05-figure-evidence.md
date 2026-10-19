# Figure evidence and source-typed chunks

## What changed and why

The reader now separates figure captions, original visual evidence, authors' discussion, prose, and table rows. A graph can be shown faithfully without asking a vision model to interpret it. No values are guessed from bar heights, colors or isolated labels.

## Follow the code

1. `backend/app/modules/documents/figures.py` groups measured words into caption lines and finds significant embedded images. A uniquely nearby image becomes a crop; uncertain or vector-only graphics use the whole source page. Explicit Figure-number references connect authors' passages, rather than assuming nearby text explains a graph.
2. `reader.py` produces version-v5 layouts. Caption words and text inside known image regions stay out of ordinary prose. Original bytes, raw extraction and measured words remain available.
3. `chunks.py` makes deterministic prose, table-row and figure-caption records. Rows keep their cells together. Caption chunks explicitly record that no image interpretation occurred. If a figure has no reliable boundary, ordinary prose on that page is held out of retrieval to prevent graph labels becoming misleading sentences. This costs recall; the page remains readable and its caption remains eligible.
4. `processing.py` publishes chunks with pages and completion status in one database transaction. Migration 0006 adds evidence_chunks. Content/version-based IDs make repeats harmless, and earlier chunk versions are retained. Future retrieval must select the correct current source version. Retaining chunks alone is not a complete historical reader/version-history UI.
5. The owned `/projects/{project}/documents/{document}/figures` endpoint returns actual source metadata. `figure-card.tsx` shows captions, page links and optional previews. `pdf-canvas.tsx` checksum-verifies the original before rendering and cropping it locally.

## Benefits and tradeoffs

- No vision API cost or external image transfer. Automatic detection still misses unusual captions, multi-panel layouts, or uncaptained vector graphics; this is not universal figure detection.
- A preview is opt-in, with one active card preview per reader page and a three-megapixel canvas budget. It still downloads/parses the PDF for that renderer, so a preview can cost an additional transfer and some memory.
- Page fallback preserves verifiability when cropping is uncertain. Holding ambiguous page prose out sacrifices retrieval coverage for clearer evidence boundaries.
- Separate embedding and answer models remain the plan. These are source chunks, not embeddings: Google credentials, vector indexing and cited chat generation are still pending. No provider call occurs in this feature.

## Try it

Open an existing document and select Update readable text and highlights. After processing, visit PDF page 9 of the supplied paper. Its Figure 1 card offers a preview, source-page navigation, and linked authors' discussion. Check narrow-screen stacking yourself; browser screenshot automation is intentionally not used.

Deferred project conflict reconciliation and Trash/restore/retention/purge remain required follow-ups. This phase adopts no purge policy and removes no originals.

Selection uses separate figure and caption URL targets: View figure highlights only the image rectangle, View caption only its measured words, and passage links only their text. Without an image boundary, Open source page does not guess a rectangle; Preview source page displays the whole page.


## Numbered equation grouping — 19 October 2026
Reader v6 isolates conservative compact display-equation runs ending with a right-aligned equation number and containing mathematical font glyphs and equality. This fixes the supplied paper's physical page 17: all 22 components (word indices 24–45) form one passage, separate from the following paragraph. PDF drawing order and measured boxes are preserved; no LaTeX reconstruction or glyph correction is claimed. Unusual mathematical font boxes can be imperfect. Undecodable private-use glyph passages show a warning and are excluded from prose chunk preparation (chunker source-types-v2). This sacrifices recall rather than asserting damaged equations. Detection is conservative and does not cover all equations. Existing uploads need Update readable text and highlights. Original bytes and raw text are unchanged. Ruff/mypy, 52 backend tests, 43 frontend tests, lint/types/build pass; full supplied paper parsed locally with the regression verified. Deferred release/lifecycle work remains unchanged.


## Numbered regression tables — 19 October 2026
Reader v7 extends bounded shaded-table detection to sequential numbered model columns, merges adjoining coefficient/error shading and includes partial-width bands. Measured empty gutters must validate all boundaries; blank cells are retained. Supplied paper physical page 18 / printed 392: one seven-column, 20-row table, with coefficients and standard errors together and model blanks preserved. Page-8 two-column table still detected. Header cells have column scope in the reader; empty cells say Blank in source and have no active highlight action. Chunker source-types-v3 includes each column heading with model-table row values and marks blank source cells explicitly. This is conservative recognition of this table family, not universal table parsing or statistical interpretation. Existing uploads require Update readable text and highlights; original and raw text remain unchanged.


## Grouped table subcolumns — 19 October 2026
Reader v10 preserves repeated parent/leaf headings as separate anchored columns when measured body gutters support the split. Parent headers are repeated with each leaf (for example Firm-weighted Share versus Firm-weighted Rank). Physical page 33 / printed 407 has five columns and 32 rows; New Orleans retains 7.4, 5, 4, 37 separately. Prior page-8, page-18 and page-20 table shapes remain intact. Chunker source-types-v4 includes each flattened column heading with row values; ambiguous crossing gutters are marked and their table rows are withheld from retrieval, with a reader warning. This is conservative grouped-header support, not general merged-cell inference. Existing documents need Update readable text and highlights. All originals/raw text retained.

