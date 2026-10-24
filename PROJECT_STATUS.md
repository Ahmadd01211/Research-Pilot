# ResearchPilot project status

## Draft protection - 25 October 2026

Unsaved writing now survives query refreshes and failed saves. In-app navigation and Back/Forward require an explicit discard choice; reload/close request the browser warning. Conflicts show local and current server text with explicit choices; keeping local text requires a separate revision-checked save. Typing during a save is retained. No browser draft storage or crash recovery is claimed. The app entry point uses React Router's data router around existing routes. Frontend 80 tests, lint, typecheck and build passed (existing bundle-size warning). No API, migration or runtime configuration changes. Work is isolated on feat/draft-protection from 9d4210a; shared runtime is unchanged. See docs/learning/14-writing-drafts.md.

## Direct evidence and writing navigation - 24 October 2026

The dashboard and sidebar now open Evidence and Writing without visiting a project overview first. With one active project, the action opens that project directly; with several, a short project chooser shows the matching destination. Project cards also link straight to both tasks, and the current-project sidebar keeps them reachable while working. No API or ownership rules changed. Frontend lint, typecheck, production build and all 74 tests passed. Visual browser review remains for the user.

## Editable export snapshots - 24 October 2026

Exports now include owner-scoped XLSX reference records and DOCX writing drafts alongside CSV and Markdown. Migration 0015 extends the export-kind constraint; the same request idempotency, draft revision checks, immutable download history, 2 MB file limit and 100 MB project limit apply. Excel metadata is stored as literal cells, including formula-looking titles. Word headings are basic and other Markdown or citation markers stay literal. The isolated backend suite passed 151 tests; Ruff and strict mypy passed. Frontend 70 tests, lint, typecheck and build passed. Browser visual acceptance and public-release export retention remain open. See `docs/learning/15-export-snapshots.md`.

## Persistent Research Chat - 22 October 2026

Research Chat supports project-owned saved threads and multi-turn follow-ups. Each turn preserves selected paper IDs, cited source text, physical PDF page, source hash, reader version and model response, so later reprocessing does not rewrite the citation history. Up to six prior turns are provided as untrusted context; new claims must cite freshly retrieved evidence. Migration 0014 is applied, generated API types are current, and the local stack is healthy. Frontend production build, Ruff and strict mypy pass. Live provider quality remains unverified until embeddings and answers are configured. Budgets, metering and thread retention controls remain future work. See `docs/learning/16-persistent-research-chat.md`.

## Docling parser pilot — 22 October 2026

An isolated Docling 2.141.0 pilot parsed the supplied 41-page paper without changing production ingestion. It reconstructed page 8 definitions and page 34 appendix rows well, but merged or shifted cells in dense regression tables, including placing Table 7's venture-capital coefficient on the following row. It exposed only one structured hyperlink against 17 original PDF link annotations and included repeated journal logos as pictures. The current reader's seven reviewed retrieval questions remain 7/7 in the offline lexical baseline. Keep Docling as a candidate behind source-quality checks, not a wholesale replacement. See `docs/DOCLING_PILOT.md` and `backend/scripts/docling_pilot.py`.

## Back-matter retrieval boundary — 21 October 2026

The real paper's printed page 400 had one passage combining acknowledgments, data availability, ORCID and endnote 1; it was eligible as body evidence. Reader v22 now separates recognized back-matter sections and numbered endnotes across pages, resets at appendices, and chunker v12 excludes administrative roles while keeping data availability and individual endnotes with role labels. A synthetic PDF regression and the full 130-test isolated backend suite passed; Ruff, strict mypy and the web production build passed. The original 41-page paper produced 378 eligible chunks with 7/7 reviewed answers covered and 7/7 top-five hits in the offline lexical baseline. The local stack was rebuilt and all services and API readiness are healthy. Existing uploads require an explicit reader update and, if previously indexed, new embeddings. See `docs/learning/07-general-pdf-extraction.md`.

## Export snapshot slice — 21 October 2026

Reference CSV and writing-draft Markdown snapshots, owner-scoped download history and idempotent creation are implemented. Migration 0013 adds immutable file records. The isolated backend suite passed 129 tests, including formula-safe CSV and unchanged historical downloads; frontend lint/typecheck, 66 tests and production build passed. Migration 0013 is live; API readiness passes and the local services are healthy. Browser visual review remains for the user. The formats are raw metadata and Markdown, not formatted citations or DOCX/XLSX. See `docs/learning/15-export-snapshots.md`.

## Writing draft slice — 21 October 2026

The Writing Studio now stores researcher-authored Markdown drafts with explicit save status, heading outline, reference-marker insertion, immutable version history and project-scoped citation validation. Migration 0012 adds drafts and snapshots. Backend owner/revision/version tests and frontend insertion test pass; see `docs/learning/14-writing-drafts.md`. This is a source-linked draft editor, not yet rich-text, AI co-writing, formatted citations or export. The local API, web, dispatcher and worker are healthy after migration 0012; the readiness check passes. Browser visual review remains for the user.

## Reference Manager slice — 21 October 2026

Researcher-verified bibliography CRUD, project citation-style preference, exact DOI duplicate blocking, probable title/year warnings, PDF linking, owner scoping, revision conflicts and soft removal are implemented. Migration 0011 adds records and settings. Backend 125 tests, Ruff and strict mypy, frontend lint/typecheck, 64 tests and build passed. The local stack was rebuilt with migration 0011 before the writing slice; browser visual acceptance remains for the user. Formatting, export and automatic metadata lookup are not claimed. See `docs/learning/13-reference-manager.md`.

## Candidate gap analysis slice — 21 October 2026

The gap workspace accepts researcher-authored hypotheses linked to active matrix cells, preserving the route to original PDF evidence. It displays supporting and challenging notes separately and derives transparent uncertainty labels from the number of supporting papers, linked challenges and stale source records. It never treats a blank matrix field as proof of absence in the literature. Owner scoping, archived-project restrictions, revisions and soft removal are enforced by FastAPI. Migration 0009 adds gap and evidence-link tables; migration 0010 versions matrix cells so editing a cited note cannot break an existing gap's provenance. The final isolated backend suite passed 123 tests, Ruff and strict mypy passed, and frontend lint, typecheck, 64 tests and production build passed. All local services and the API readiness check are healthy after deployment. Browser visual review remains for the user. See `docs/learning/12-candidate-gaps.md`.


## Literature matrix slice — 21 October 2026

The next phase adds an owner-scoped, user-authored evidence matrix. Each populated research question, method, sample, finding, or limitation field requires a current eligible source chunk from the selected paper. The backend persists a separate source-linked cell for each field, rejects duplicate fields and mismatched documents, and uses row revisions to protect concurrent edits. Rows can be soft-removed; archived projects remain readable. The UI is a real comparison table with a per-page source picker and version-checked PDF links. The new migration is 0008. The isolated backend suite passed 121 tests; Ruff and strict mypy passed. Frontend lint, typecheck, 63 tests and production build passed. Local API, database, dispatcher, worker and web are healthy; the API readiness check succeeds and the matrix route serves. No browser visual acceptance has been completed. See `docs/learning/11-literature-matrix.md`.


## Cited Research Chat preview — 20 October 2026

The next vertical slice now has a project-linked Research Chat page and a server-side answer endpoint. It retrieves at most eight current, owner-scoped evidence chunks from selected indexed papers and uses a separately configurable Google answer model to produce short statements with source IDs. The server rejects unknown citations, links each statement to an excerpt and original PDF location, and returns an explicit insufficient-evidence state. The feature is disabled by default because no Google key is configured. Provider output and real semantic quality have not been live-tested. The chat is single-turn and does not persist history; source IDs validate provenance but cannot prove a generated claim is true. See `docs/learning/10-cited-research-chat.md`.

Verification: 119 isolated backend tests, Ruff and strict mypy passed; 62 frontend tests, lint, typecheck and production build passed. Local API, web, dispatcher and worker are healthy after rebuilding. Existing application data and volumes were preserved. Browser interaction and a real Google call remain unverified.


## Continued categorical table fix — 20 October 2026

Reader v21 recognizes measured continued tables with up to eight numbered data columns and categorical Yes/No cells. The user's page 22 had previously been one oversized readable passage; its quality gate correctly withheld the unstructured page from retrieval. The new parser produces an 8-column source table with five separate rows and keeps Notes outside the table. A synthetic PDF regression and the original read-only PDF verified the result. The affected uploaded paper was refreshed in place: page 22 is now checked, has six table rows including its header, and has five current-version row chunks. Old derived evidence remains versioned and is not used by current-version indexing. Other stored papers with old layouts need an explicit reader update when used.

## Evidence search UI checkpoint — 20 October 2026

The project now links to a real source-scoped evidence search page. It displays provider availability, all project papers and their current index state, explicitly starts eligible indexing, lets researchers select ready papers, and shows ranked passages with version-checked original-PDF links. Prose and caption results use their exact anchors; table rows link to the page for verification. It deliberately does not present retrieved text as an AI-written answer. Hosted search remains disabled until a server-side Google key is configured; no live provider request or visual browser acceptance has been completed. The checked OpenAPI contract and frontend types were regenerated. Backend 114 tests, frontend 62 tests, Ruff, strict mypy, frontend lint/typecheck and build passed. Next: configure/evaluate real embeddings with reviewed questions, then add cited Research Chat and insufficient-evidence handling.

## Embedding search checkpoint — 20 October 2026

Versioned Google Embedding 2 indexing and owned, selected-paper vector search are implemented behind an opt-in server-side key. Migration 0007 is applied additively; the local stack is healthy. Source chunks are sent in bounded worker batches only after a researcher explicitly requests an index. Search returns ranked, page-linked evidence with source IDs and distances, not generated answers. Provider calls and actual semantic retrieval quality remain unverified because no Google key is configured. The existing 113 backend tests pass, including a fake-provider end-to-end vector search; Ruff and strict mypy pass. See `docs/learning/09-embedding-search.md`. Next: integrate an evidence UI and cited Research Chat, evaluate real-vector retrieval on reviewed papers, and design failed-index retry/recovery. Existing deferred password recovery, project edit conflict reconciliation, and removal retention/purge remain open.

## Retrieval baseline checkpoint — 20 October 2026

An offline evaluation now pins seven reviewed questions to the supplied paper's exact checksum and measures whether eligible chunks contain their answers and where a deterministic lexical search ranks them. Reader v20 removes clearly smaller first-page publication notices from research evidence while retaining them in readable/raw source views. Chunker v11 adds a unique nearby table caption to each row's search text. The local 41-page sample produced 373 eligible chunks; all seven reviewed answers were present and all seven appeared in the top five (six first, one second). The earlier baseline was 375 chunks and six top-five hits. This run used bundled pdfplumber 0.11.9 while the backend image pins 0.11.10; repeat the evaluation in the backend image before calling it a production-parser score. See `docs/learning/08-retrieval-evaluation.md` for commands and limits. Google embeddings, vector retrieval, Research Chat and answer generation remain unimplemented. Existing uploads need an explicit reader update for these versioned changes.

Updated: 20 October 2026. Branch: feat/source-reader. The tested Vite/identity foundation is checkpointed in local Git. No remote/PR or public deployment exists.

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


## Unnumbered sectioned numeric tables — 19 October 2026
Reader v11 adds caption-validated, shaded-header unnumbered numeric tables with aligned leaf headings and measured source boxes. The supplied paper physical page 34 / printed 408 yields 38 rows and four columns: row label plus AI usage rate (%) Yes, No and Difference. Full-sample 6.0 remains outside the comparison rows. Section labels and quoted subsections remain source rows; chunker source-types-v5 carries their context into each data row and skips section-only chunks. Uncertain numeric alignment is marked and its table rows withheld from retrieval. This supports a conservative single-line numeric-table family, not arbitrary unnumbered or multiline tables. Existing uploads need an explicit reader update; originals/raw text unchanged. The synthetic corpus adds sectioned-numeric and ambiguous-sectioned-numeric cases (17 layouts total).


Verification for unnumbered sectioned numeric tables: all 71 backend tests and 48 frontend tests pass; Ruff and strict mypy pass (40 source files), frontend lint/types and production build pass. Final 41-page source parse confirms exact 8.4/5.3/3.1 values and earlier page 8/18/20/33 table structures. Seventeen-case quality report refreshed.


## Partial-shading summary table — 19 October 2026
Reader v12 collects partial-width row shading inside a full-width header/closing-rule boundary, while retaining gutter validation. The supplied paper physical page 7 now yields six columns and seven rows, preserving all five numbered sample headings and six data rows; Employment (unweighted) remains distinct from Employment (weighted), as do age and observations. Paragraph-to-caption boundaries are explicit for uppercase TABLE plus an identifier, and Notes/Note starts; skipping measured table/figure regions flushes prior prose so captions do not join subsequent notes. Raw bytes/text remain unchanged. Existing uploads require an explicit reader update. Eighteen synthetic layouts now include a partial-shading summary table with wrapped row labels, separate prose/title/notes and labelled row chunks. All 72 isolated backend tests, Ruff and strict mypy pass; prior source tables on pages 8/18/20/33/34 remain detected. Frontend source unchanged in this slice.


## Numbered section boundaries — 19 October 2026
Reader v13 starts a new passage at a numbered title line larger than nearby body text, excluding table/figure/equation words and recurring margins. It uses numbered-line geometry and local text-size comparison, not paper-specific headings or page numbers. Page-8 section 3.3 now begins at its own first token (index 170) with following section text; prior discussion is excluded from that passage and the ten-row table remains intact. Same-size bold-only and unnumbered headings are not guaranteed. Corpus now has twenty layouts, adding a numbered-heading positive case and same-size decimal-prose counterexample. Original/raw text retained; existing uploads require reader update.


Numbered-heading verification: all 74 isolated backend tests, Ruff and strict mypy pass. The actual 41-page paper parses locally with section 3.3 correctly beginning its passage. Twenty-layout report refreshed. Frontend source unchanged.


## First-page source metadata roles — 19 October 2026
Reader v14 conservatively separates first-page publication metadata, title, authors, affiliations, correspondence, funding and abstract using explicit Abstract/Introduction anchors, title size and measured sidebar geometry. Unsupported/rotated/unanchored layouts retain existing reading rather than inferred roles. Passage role is additive and defaults to body for old data. Supplied paper first page yields seven distinct role blocks with a coherent 210-word-token abstract, followed by introduction/body text. Source anchors and raw text remain unchanged. Chunker source-types-v6 excludes classified metadata from research-evidence chunks and records body/abstract evidence_role. UI labels metadata and explains that Reference Manager records are not automatically updated. This is not validated author/DOI parsing, a full first-page metadata service, or general copyright/footer removal. Existing documents need explicit reader upgrade. Corpus now has 22 layouts, including positive sidebar metadata and missing-body-anchor fallback.


Front-matter verification: all 76 backend tests and 49 frontend tests pass, Ruff/strict mypy pass (41 source files), frontend lint/types/build and regenerated OpenAPI/types pass. Twenty-two-case quality report refreshed. Source-metadata blocks remain highlightable while excluded from generated evidence chunks; abstract remains eligible.

## Passive PDF links and automatic quality gates — 19 October 2026

Reader v15 adds source-linked HTTP(S)/simple-mailto/direct-and-named PDF destinations plus visible complete URL/DOI capture, with bounded parsing and no network fetching/action execution. Cropped/rotated annotation coordinates come from the root page before normalization. Unsafe and unsupported actions are disabled; unresolved destinations are not guessed. Source links carry page boxes, measured text and source anchors. Chunker source-types-v7 associates safe link destinations as metadata and enforces versioned evidence-quality-v1 gates before publishing chunks. Automatic assessments flag unstructured/ambiguous tables, bad anchors/boxes, undecodable/fragmented/numeric text, uncertain figures and unsupported metadata/empty pages; original/raw/readable content remains inspectable. Owned document quality endpoint and reader panel summarize current page states and review navigation. Old/stale layouts are Not assessed; current preparation is automatic for new uploads, while existing originals require explicit reader upgrade. No model calls or linked-webpage ingestion occurs.

The supplied 41-page paper retained 60 allowed external/email/DOI links and 359 internal links; current checks produced 29 checked pages, six needing review and six with evidence withheld. More unsupported tables are exposed rather than silently indexed. These heuristics do not guarantee correctness; conservative withholding reduces recall. No retention/purge/conflict policy changes. See learning/06-links-and-quality.md for actual code flow, states and limits.

Verified locally: 97 backend tests and 55 frontend tests passed; Ruff, mypy, frontend lint/type checks and production build passed. Deployed upload/worker/link/quality and PDF-reader smoke checks passed. Existing documents require an explicit reader update; new uploads are assessed automatically.



## Shared table extraction and chunk contract

Reader v16 supports captioned shaded-header numeric tables with numbered multiword column headings and section rows, even without alternating body-row shading or a closing rule. Header starts define measured column boundaries; inconsistent numeric rows and word-crossing boundaries remain ambiguous and are withheld. Raw source bytes and text are unchanged.

Chunker source-types-v8 shares labelled row and section handling across numbered model, model subcolumn, labelled, and numbered section adapters. Adding a detector must also pass the shared chunk-contract tests so a new layout cannot silently emit unlabelled numeric rows. Body/abstract passages, table rows and figure captions stay separate; source anchors, safe links, deterministic versioned identities and automatic quality gates remain in place. This is a conservative local parser, not universal document understanding or OCR.

The supplied paper physical page 14 now yields 38 table rows and five columns. The advanced-degree evidence is: Full sample 22.4; Use AI 31.5; Do not use AI 21.9; Difference 9.6, with its owner-characteristics section retained. Previously fixed pages 7, 8, 18, 20, 33 and 34 retain expected table dimensions. The 23-layout synthetic corpus and four shared adapter-contract cases run automatically in the backend suite. Existing documents require reader update once; new uploads use the current pipeline automatically.

Verification: 102 backend tests, 56 frontend tests and 23 real-PDF synthetic layouts pass. Ruff, strict mypy, frontend lint/type checking and production build pass. Supplied-paper page-14 labelled row values and prior table dimensions verified locally; deployed reader and link/quality smoke checks pass. No embeddings or provider requests introduced.


Figure preview association fix: figure captions above or below a nearby embedded image can now receive a focused crop, provided the nearest image match is unambiguous. Ambiguous/vector-only figures retain the full-page fallback. Existing documents need reader update once.

## General PDF extraction safeguards and continued tables — 19 October 2026

Reader v18 adds a layout-based continued-table detector for numbered columns and aligned numeric rows. It preserves repeated headers and row labels in each row chunk; notes remain separate prose. The detector is paper-independent. Quality assessment v2 now recognizes a validated table whose measured bounds include or immediately follow its caption, so supported continued tables do not spuriously suppress nearby prose. Uncertain/inconsistent table structure is still flagged and its table rows are withheld from retrieval.

The reader toolbar includes a validated physical-page jump. Original PDF bytes and raw extracted text remain authoritative and unchanged; readable layouts and chunks are derived, deterministic and versioned. New uploads use the current parser. Existing extracted documents need the explicit reader update before current assessment/chunks are available. No embeddings, vector retrieval or model calls are introduced here.

This is safer general PDF processing, not a promise to understand every PDF. Scans still need OCR; complex multi-column reading order, unusual tables, equations, handwriting and font-encoded glyphs can remain uncertain. Automatic checks detect known integrity/layout risks but cannot certify meaning or numerical accuracy. When unsure, preserve the source, report the limitation and withhold only affected evidence rather than silently guessing.

Verification: 105 backend integration/corpus tests and 59 frontend tests pass; backend Ruff/strict mypy, frontend lint/types and production build pass. The 24-case synthetic PDF suite includes the generic continued-numbered-table adapter. The supplied McElheran PDF physical page 15 now has a 5-column continued table and two correctly labelled retrieval rows; the old unstructured-table prose block is removed while link warnings can still keep the page in “Needs review.” No user originals or application volumes were deleted.

Read `docs/learning/07-general-pdf-extraction.md` for the pipeline, tradeoffs, versioning, testing strategy and page-number convention.

## Grouped regression-table extraction — 19 October 2026

Reader v19 adds a reusable detector for numbered regression model columns with multi-line/grouped headings. It maps cells by measured column starts, preserves blank estimates, joins separate parenthesized standard-error lines to each coefficient, excludes page-edge publisher text from labels, and stops when content inside numeric columns no longer matches the expected structure. Chunker source-types-v10 places each table row, its label and its model headings together; the reader marks model headings as accessible column headers.

The supplied McElheran paper's physical page 21 (printed page 395) now yields 18 data rows by seven model columns. The “Full owner and revenue sample” heading is complete, coefficient and standard-error pairs remain together, missing estimates remain blank, and the page passes structural checks with 18 row chunks. A synthetic PDF test covers split errors, missing cells, offset grouped headings and publisher text sharing a row baseline.

Verification: all 107 backend tests, Ruff and strict mypy pass; all 60 frontend tests, lint, type check and production build pass. The generated extraction report covers 25 synthetic layouts. This is generalization across tested layout patterns, not a guarantee for every PDF; scanned pages, unusual model headers and ambiguous alignment still require review. Existing uploads need the explicit reader update to use v19. Source files and application data were preserved.
