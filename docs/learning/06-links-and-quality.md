# Source links and automatic evidence assessment

## What happens automatically

New PDF ingestion now prepares reader v15 layouts, source links, deterministic page assessments and gated source chunks in the existing atomic background-processing transaction. It requires no model API key and performs no linked-page fetching. Existing extractions retain their originals and versions; the user explicitly updates the reader once to produce current evidence.

The reader's Automatic source checks panel shows document-wide counts and page findings. Each flagged page can be opened directly. Old or stale reader/assessment versions show Not assessed, rather than a successful current check. There is no fabricated confidence percentage or blanket RAG-ready badge.

## Follow the implementation

1. `links.py` reads link annotations from the original page coordinate system and clips/normalizes their boxes into the rotated CropBox used by the viewer. It associates measured words and passage/cell/figure anchors. HTTP(S), simple mailto, direct internal destinations and named internal destinations are supported. Visible complete URLs and bare DOIs are also retained when present. Broken, unsupported or unsafe actions are disabled or marked unresolved; no PDF actions execute.
2. `reader.py` assigns versioned link identities after passage anchors exist and runs `quality.assess_page`. The PDF subprocess still has its original memory/CPU/time limits. Limits include 500 annotations/links per page, 5,000 retained links per document and 2,048 characters per accepted destination. Parsing no longer depends on a linked website being available.
3. `quality.py` checks measured boxes/anchors, inconsistent or ambiguous tables, printed table captions without validated tables, dense numeric prose, uncertain figure boundaries, undecodable symbols, fragmented text, unclassified publication metadata and empty measured pages. Link warnings are separate from text eligibility. Links intentionally attached only to excluded margin text do not make the page need review.
4. `chunks.py` re-evaluates the gates before publication. It withholds affected passages/tables or whole-page prose, and invalid page anchors withhold all chunks on that page. Other eligible evidence remains available. Safe link targets and internal page numbers attach as chunk metadata by matching source anchors; hidden URLs are not appended to prose. Chunker source-types-v7 records assessment identity.
5. The owned `GET /api/v1/projects/{project}/documents/{document}/quality` endpoint reads only compact JSON projections and reports the latest reader/assessment status for every page. Foreign and removed projects return 404; incomplete extraction returns 409. `source-diagnostics.tsx` renders page/document findings, explicit external links, internal navigation and independent source-location highlights. It checks URL protocols again before rendering anchors.

## Safety and provenance

External links require an explicit user click, open with noopener/noreferrer and no referrer, and are not fetched by the application for RAG. JavaScript, local file, remote-file navigation, launch and other unsupported actions are disabled. URL credentials, control characters and unsupported protocols are rejected. This is action/protocol handling, not a reputation guarantee for external sites. A link's content is not evidence unless separately ingested in a future workflow.

Original bytes, raw text and readable source remain available even when derived evidence is withheld. Link targets/boxes/anchors and page assessments live in existing page JSONB, requiring no destructive migration. Previous chunk versions are retained; future embedding/indexing must select current source/reader/chunker/assessment versions. No embeddings or chat model is called by this phase. Trash, conflict reconciliation, retention/purge and password recovery remain deferred as previously recorded.

## States and tradeoffs

- Checks passed: these implemented checks found no issue. This does not certify semantic or numerical correctness.
- Needs review: one or more warnings or selective evidence gates apply, while some units remain eligible.
- Evidence withheld: no eligible units remain under the implemented checks, or page-wide integrity checks fail. The PDF is still readable.
- Not assessed: no matching current assessment exists. Update the reader; stale results do not masquerade as current ones.

The rules deliberately trade retrieval coverage for less misleading evidence. They can have false positives and false negatives, cannot recognize every table/formula or publisher layout, and do not perform OCR. A scanned or unsupported page needs another extraction method or review. Visible URLs split across lines without annotations may not be reconstructed; unsupported destinations remain unresolved rather than guessed. Generic layout detection does not imply every document is fully understood.

## Verification

The synthetic regression suite covers direct/named/missing destinations, hidden external URLs, visible DOI targets, scripts and remote-file actions, URL validation, link limits, owner-scoped reporting, stale assessments, valid/invalid anchors, selective formula withholding, unknown tables, inconsistent rows, empty/fragmented pages and cropped pages at 0/90/180/270 degrees. Frontend regressions cover safe external anchors, internal navigation, quality states, unknown link identities and switching between link-location and passage highlights.

The supplied 41-page paper was assessed locally without provider calls: 60 allowed external/email/DOI links and 359 internal page links were retained. The observed assessment found 29 pages without flags, six needing review and six with evidence withheld. This exposed additional unsupported tables instead of silently marking them ready. These are results for this reader/check version, not an accuracy score.

Run the normal disposable backend suite and frontend checks before changing these rules. `scripts/smoke_links_quality.py` additionally exercises real upload/worker/storage/HTTP behavior using an explicitly supplied synthetic fixture. The existing extraction corpus report now records each synthetic page's assessment and finding codes.

Verified locally: 97 backend tests and 55 frontend tests passed; Ruff, mypy, frontend lint/type checks and production build passed. Deployed upload/worker/link/quality and PDF-reader smoke checks passed. Existing documents require an explicit reader update; new uploads are assessed automatically.

