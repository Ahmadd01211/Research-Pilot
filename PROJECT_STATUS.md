# ResearchPilot project status

Updated: 19 October 2026. Branch: feat/source-reader. The tested Vite/identity foundation is checkpointed in local Git. No remote/PR or public deployment exists.

## Working local application

http://localhost:3100/projects — React/TypeScript/Vite, FastAPI, PostgreSQL/pgvector, Redis and independent Celery worker.

Identity/profile was manually accepted by the user. The new projects slice includes create/list/detail/edit, questions/objectives, activity, archive/restore, typed-title-confirmed soft removal, literal search, cursor pagination and actual owned dashboard cards. Edits use revisions; retries use owner-scoped request UUIDs; project changes and activity are transactional. No paper counts, research findings or AI usage are simulated in the real app.

## Verification for projects

- Backend Ruff and strict mypy passed (23 source files).
- 16 PostgreSQL/Redis integration tests passed: eight identity cases and eight project cases including concurrency and rollback. One upstream TestClient/httpx deprecation warning remains.
- Frontend lint, strict types, all 16 component/client/schema tests and production build passed. Build also passed in the Node 24 container.
- Built-app HTTP smoke passed: project persistence/retry, edit conflict, CSRF, archive/restore, activity, foreign-account denial and repeated soft removal of its own synthetic project.
- Migration 0002 applied additively; existing account/session tables preserved. API, database, Redis, worker and web healthy.
- No browser screenshot automation; user visual acceptance of the projects UI remains pending.

## Teaching and references

Read docs/learning/01-research-projects.md for actual code flow, schema/service boundaries, authorization, transactions, idempotency, optimistic concurrency, pagination and alternatives. ADR 0003 records project decisions. The twelve user reference images remain unchanged, with findings in docs/REFERENCE_IMAGE_REVIEW.md. The earlier synthetic design export remains separate from the real application.

## Remaining scope

User explicitly approved implementing password recovery later while proceeding with research features. It remains required before public release: real mail delivery, expiring single-use reset tokens, generic account-discovery responses, throttling and session revocation. Opaque cookie sessions remain in place; the newer access/refresh wording still needs its separate decision.

Private PDF storage and durable page-linked text extraction are now implemented; current verification is below. Next: version-aware chunking, embeddings and source-scoped RAG. Explicit document replacement/version-history UI remains pending. No AI inference or manuscript generation is implemented yet.

Soft deletion is retention, not a backup or a permanent erasure policy. Removed-project recovery/purge UI is not implemented. Production trusted-proxy abuse controls, account verification, backup/restore, dependency/container hardening and metering remain tracked in SECURITY.md.

Test smoke used synthetic development accounts; only its own synthetic project was soft-removed. No real user project, uploaded document, application Docker volume, design reference or old D: application was deleted or changed by test setup.


## Historical storage-only checkpoint — 19 October 2026 (superseded below)

Project detail → Open research library → Upload PDF. The real library includes a semantic paginated table, actual counts, empty/loading/error/success states, private original download and duplicate notices. Archived projects are readable but reject uploads; removed/foreign projects hide document endpoints. Generated contract includes the raw binary PDF request.

Upload screening: 20 MiB maximum, bounded filename, content type and PDF signature. This is **not parser validation**. Immutable originals use UUID filenames in a private named Docker volume; checksums deduplicate within the project. Finalization rechecks lifecycle/ownership and locks the project to serialize quotas and concurrent retries. Per-project limit: 100 papers or 200 MiB. Stored is the only processing status; no extraction, indexing, OCR or RAG readiness is claimed. Revisions/versions and durable worker jobs remain next.

Verification: backend Ruff and strict mypy passed (29 source files); all 24 isolated PostgreSQL/Redis integration tests passed, including eight document cases, concurrency, safe storage errors and migration parity. Frontend lint/typecheck, all 20 tests and local/container production builds passed. Built-app HTTP smoke passed through Nginx with a >256 KiB synthetic PDF fixture, exact download bytes, list and renamed duplicate. Migration 0003 applied additively. Existing account/project data and Docker volumes were preserved. One upstream Starlette/httpx warning remains. User visual acceptance of the library remains pending; no screenshot automation used.

Read learning/02-private-pdf-library.md and ADR 0004 for actual code flow and tradeoffs. Staging cleanup covers normal request outcomes; crashes may leave staging files. Published files are retained on ambiguous commit failures to avoid loss; orphan reconciliation, coordinated backups, production object storage, upload abuse/time limits and full PDF validation remain release work. The smoke created one synthetic development account/project/original and retained it; it did not alter real user documents.

## Deferred follow-ups agreed with the user — 19 October 2026

Continue the research feature phases now. Revisit these items earlier if a dependent feature requires them, otherwise during release hardening before public release:

- Edit conflicts: preserve unsaved input; compare the user's changes with latest saved fields; offer review/reapply or loading the latest version. Consider automatic merging only for non-overlapping field changes; recheck revisions on final save. Existing stale-write rejection remains in place. No collaborative editor is required for personal project settings.
- Removal lifecycle: design Trash/restore, a clearly communicated retention window, confirmed permanent deletion, and an idempotent purge job covering originals, versions, extracted evidence, embeddings and database rows. Coordinate processing cancellation and retries; document backup expiration separately. The proposed 30-day window is a recommendation, not an adopted retention policy. Current soft removal retains data and hides access; no recovery/purge UI exists yet.

While implementing ingestion, preserve the ability to cancel processing and clean up derived artifacts later. Deferral does not authorize automatic purging of current user data.


## Current PDF processing phase — 19 October 2026

Working: new uploads persist a PostgreSQL processing job with original metadata; dispatcher publishes to Redis/Celery; independent worker validates/checksums and extracts page-linked text in a bounded Linux subprocess. Migration 0004 backfills retained originals; removed projects start cancelled. UI displays Queued, Extracting text, Text extracted, Needs attention or Cancelled; polls pending rows; offers eligible retries and a source-text page viewer with provenance and original download. No fake progress/indexing/OCR is claimed.

Reliability: durable job rows double as transactional outbox intent; redispatch handles lost publications; UUID leases fence duplicate/stale results. Expired leases and transient failures get up to three total automatic attempts, with eligible user retries capped at five total attempts. Parsing is limited to 60 seconds wall time, 512 MiB address space, 300 pages, 100k characters/page and 2m/document. Pages, status and completion activity publish atomically. Existing source files remain immutable, and original checksum/extractor identity accompany evidence. Resource-limited subprocesses are not a complete hostile-code sandbox or malware scanner.

Access/lifecycle: all evidence/retry endpoints scope to current user's live project. Archive permits already accepted extraction but blocks uploads/retries. Removed projects cannot publish new extracted pages at claim/finalization. Deferred conflict resolution and Trash/retention/purge remain recorded and unimplemented. No automatic file deletion or new retention period was introduced.

Verification: Ruff and strict mypy pass (35 source files); all 37 backend integration cases pass against isolated PostgreSQL/Redis with temporary storage. All 24 frontend tests, lint, types and local/container builds pass. Real built-app HTTP smoke passed through dispatcher, Redis, Celery, parser and database: a valid two-page PDF extracted with correct source page, original roundtripped, duplicates did not reprocess, malformed PDF failed honestly. Migration/model parity passed. One upstream Starlette/httpx test warning remains. No screenshot automation; user visual review is pending. Existing app volumes/data preserved; synthetic smoke accounts/projects/documents retained.

Read learning/03-durable-pdf-processing.md and ADR 0005 for code flow, failure categories and tradeoffs. Next research phase: chunking/embedding identity, owned source-scoped retrieval and Research Chat with citations and abstention. No embedding provider is configured/called yet. Explicit replacement/version history, OCR, stronger parser sandboxing, artifact reconciliation/backups and prior public-release work remain pending.


## Current source-reader milestone — 19 October 2026

Original-format reading now uses lazy self-hosted PDF.js 6.4.299 with actual source layout, zoom and synchronized pages. Reader supports PDF+text, PDF-only or text-only views and responsive stacking. Raw pypdf transcript remains separate from readable measured-word passages. Select Show passage in PDF to highlight saved word boxes; links include physical page, deterministic passage anchor, original checksum and reader/parser version. Unknown/mismatched anchors and invalid pages never silently select another source. The browser checksum-verifies originals before rendering. Security policy was not relaxed; XFA/WASM are disabled, local inert image fallbacks/fonts/CMaps are served, and module workers have the proper JavaScript MIME type.

Extraction now adds pdfplumber/pdfminer word coordinates in rotated CropBox space. Font-relative segmentation improves tight typesetting. Reader version word-passages-v3 plus parser identities captures the cleanup rule; repeated edge/side-margin text is excluded only after recurrence across at least three/40% of pages and remains inspectable. No spelling, citation/number repair or AI rewriting occurs. All raw text remains available. Passage reading order, complex layouts and mathematical text can remain imperfect.

Migration 0005 adds nullable page layout JSONB. Existing extractions are preserved; an owned CSRF-protected Prepare readable text and highlights action queues a bounded upgrade only when needed. New uploads prepare automatically. Original PDFs are unchanged; no erasure/retention policy or conflict-resolution UI was introduced.

Verification: Ruff and strict mypy pass (36 backend source files); all 41 disposable PostgreSQL/Redis integration tests pass, including raw preservation, boxes, crop/rotation, preparation ownership and cleanup. All 34 frontend tests, lint, strict types and local/container builds pass. Static PDF.js canvas checks rendered the supplied 41-page source's first pages with measured overlays; the full bounded parser processed all 41 pages locally. Built-app reader smoke passes: real background layout extraction, checksum/original roundtrip, source deep route, worker MIME, local font/CMap/decoder assets and strict CSP. All six services are healthy. One upstream Starlette/httpx test warning remains. Actual app visual review is pending; no browser screenshot automation was used.

Google-hosted embeddings with an independently configurable stronger chat model are user-selected for the next RAG phase (ADR 0007). No provider API key, external embedding call, vector index or chat generation is implemented/configured in this reader milestone; no research content was sent to Google. Before changing source extraction after citations exist, retain cited derived versions explicitly. See learning/04-source-reader.md and ADR 0006 for implementation/tradeoffs. Existing user data, volumes, reference images and source file were preserved; smoke fixtures use synthetic accounts/papers.

## Page-8 table/order correction — 19 October 2026

Reader version word-passages-v4 separates conservatively detected alternating-shade two-column tables from prose, retains row/cell word anchors and renders semantic table cells in visual page order. Large caption/footnote gaps and backwards PDF text-flow jumps start separate prose blocks. Existing readers can explicitly upgrade through Update readable text and highlights; new uploads use this version automatically. Raw extraction/original bytes remain unchanged. General table recognition is not guaranteed: this detector requires repeated broad shading, a measured empty column gutter and a closing rule. Ambiguous layouts fall back to existing source text rather than invented cells.

Regression verified on the supplied paper: physical page 8 / printed page 382 yields one table with all ten technology/definition pairs, including the wrapped touchscreen/kiosk label. Backend suite: 43 cases. Frontend suite: 35 cases including semantic table cells and cell highlights. Ruff/mypy, frontend lint/types/build, container build and live reader HTTP smoke pass. Generated vendor PDF assets are excluded from application lint. No OCR or external AI calls were needed. User must request the reader upgrade for an existing uploaded extraction; user data is not silently reprocessed.

## Figure evidence and typed chunks — 19 October 2026

Reader v5 adds source-caption cards, reliable embedded-image crops or full-page fallback, and linked authors' passages that explicitly mention a figure. Previews are opt-in, checksum-verified and locally rendered; one card preview is active at a time. No chart interpretation or external AI call occurs. Existing uploads require the explicit reader upgrade. The supplied 41-page paper parses locally: PDF page 9 has Figure 1 with a measured crop and three explicit discussion passages; ten visual records were detected overall.

Migration 0006 adds immutable, deterministic source chunks for prose, table rows and figure captions. Publication is atomic with extraction, repeats are idempotent, and prior chunk versions are retained. Ambiguous figure-page prose is excluded from retrieval preparation to avoid mixed chart labels; raw reading remains available. Embeddings, vector retrieval and chat generation remain pending, as does complete historical reader navigation. Deferred conflict and Trash/retention/purge work remains unchanged.

Verification: 50 backend tests and 38 frontend tests; Ruff, strict mypy, frontend lint/types/build. See learning/05-figure-evidence.md and ADR 0008 for code flow and tradeoffs. No application volumes or user originals were removed.

## Figure caption highlight correction — 19 October 2026
Figure selection now highlights the measured caption words alongside the image rectangle. Captions also highlight when image boundaries are uncertain. Source/version mismatch still disables all highlights. Existing v5 extraction needs no reprocessing. Frontend lint, strict types, all 41 tests and production build pass.


## Separate figure and text targets — 19 October 2026
Supersedes combined-caption highlighting above: View figure highlights only a known image box; View caption highlights only saved caption word boxes. Passage links remain text-only. Unknown image boundaries use Open source page and Preview source page, with no guessed image highlight. Full-page previews are intentional fallback, not isolated crops. No re-extraction required. All 43 frontend tests, lint/types and production builds pass; local web deployed.


## Numbered equation grouping — 19 October 2026
Reader v6 isolates conservative compact display-equation runs ending with a right-aligned equation number and containing mathematical font glyphs and equality. This fixes the supplied paper's physical page 17: all 22 components (word indices 24–45) form one passage, separate from the following paragraph. PDF drawing order and measured boxes are preserved; no LaTeX reconstruction or glyph correction is claimed. Unusual mathematical font boxes can be imperfect. Undecodable private-use glyph passages show a warning and are excluded from prose chunk preparation (chunker source-types-v2). This sacrifices recall rather than asserting damaged equations. Detection is conservative and does not cover all equations. Existing uploads need Update readable text and highlights. Original bytes and raw text are unchanged. Ruff/mypy, 52 backend tests, 43 frontend tests, lint/types/build pass; full supplied paper parsed locally with the regression verified. Deferred release/lifecycle work remains unchanged.


## Formula glyph highlight safeguard — 19 October 2026
Undecodable private-use mathematical glyph boxes are omitted from passage highlighting because the supplied PDF reports some over the following paragraph. Correctly decoded formula tokens still highlight; all extracted symbols remain inspectable. This is partial highlighting, not repaired glyph geometry or guaranteed formula recognition. No re-extraction is needed for this UI fix. The regression asserts exact included coordinates and excludes the misplaced glyph. All 44 frontend tests, lint/types and production builds pass. Local web deployed.


## Numbered regression tables — 19 October 2026
Reader v7 extends bounded shaded-table detection to sequential numbered model columns, merges adjoining coefficient/error shading and includes partial-width bands. Measured empty gutters must validate all boundaries; blank cells are retained. Supplied paper physical page 18 / printed 392: one seven-column, 20-row table, with coefficients and standard errors together and model blanks preserved. Page-8 two-column table still detected. Header cells have column scope in the reader; empty cells say Blank in source and have no active highlight action. Chunker source-types-v3 includes each column heading with model-table row values and marks blank source cells explicitly. This is conservative recognition of this table family, not universal table parsing or statistical interpretation. Existing uploads require Update readable text and highlights; original and raw text remain unchanged.


Verification for regression-table milestone: Ruff/strict mypy, all 54 backend tests and 44 frontend tests, frontend lint/types/build and local container builds passed. Live reader smoke passed after deployment. No browser screenshot automation used; user visual review pending.

## Extraction corpus and rotated text — 19 October 2026

Twelve generated synthetic PDFs now run through the real reader/schema/chunker in pytest and a standalone nonzero-on-failure JSON quality report. Contracts cover prose, two-column token preservation, crop boxes, three rotations, definition/model tables, embedded/vector/uncaptioned figures and equation baselines. This is a development regression gate, not universal semantic accuracy or a per-upload RAG-ready classifier. Reader v8 fixes rotated word fragmentation and compares paragraph gaps in the unrotated reading axis. Static PDF.js overlays for all three rotations were inspected. Supplied paper was reparsed locally: page 8 retains ten table rows and three body passages plus title/notes; page 18 retains twenty rows/seven columns. Cell-level highlight controls remain distinct from row-level retrieval chunks.

Verification: 66 backend tests, 45 frontend tests, Ruff/strict mypy, frontend lint/types/build pass. See docs/EXTRACTION_QUALITY.md and docs/extraction-quality-report.json. Varied real publisher samples and general mathematical/multi-column semantics remain unverified. No external AI calls, no source file changes, no new retention policy. Existing documents need an explicit reader upgrade for v8.

## Wide source table navigation — 19 October 2026
User confirmed page-18 columns were available; this was not missing extraction. Wide tables now show actual column count, explicit sideways-scroll instructions and working previous/next column controls. The scroll region is labelled and keyboard focusable; two-column tables keep the simpler layout. No reader/chunker version change or reprocessing is required.


## Two-model regression table correction — 19 October 2026
Reader v9 supports two sequential numbered model columns when a nearby table caption is present, while retaining measured empty-gutter and shaded-boundary validation. Half-point closing-rule tolerance handles contiguous shading/rule coordinate rounding without creating empty rows. Supplied paper physical page 20 / printed 394 now yields one three-column, thirteen-row table: both model headings remain in its header row; title, notes and body prose are separate. Page-8 ten-row and page-18 twenty-row tables remain intact. The original synthetic corpus now contains thirteen layouts, including a captioned two-model table, and checks caption/table separation. Existing uploads require the explicit reader upgrade; original/raw text unchanged.


## Grouped table subcolumns — 19 October 2026
Reader v10 preserves repeated parent/leaf headings as separate anchored columns when measured body gutters support the split. Parent headers are repeated with each leaf (for example Firm-weighted Share versus Firm-weighted Rank). Physical page 33 / printed 407 has five columns and 32 rows; New Orleans retains 7.4, 5, 4, 37 separately. Prior page-8, page-18 and page-20 table shapes remain intact. Chunker source-types-v4 includes each flattened column heading with row values; ambiguous crossing gutters are marked and their table rows are withheld from retrieval, with a reader warning. This is conservative grouped-header support, not general merged-cell inference. Existing documents need Update readable text and highlights. All originals/raw text retained.


Grouped-header verification: 69 backend tests and 48 frontend tests pass, including exact subcolumn values, preserved blanks, ambiguous-gutter withholding and single-cell highlights. Ruff, strict mypy, frontend lint/types and production build pass. Fifteen-case quality report refreshed.

