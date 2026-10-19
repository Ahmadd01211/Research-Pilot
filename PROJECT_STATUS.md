# ResearchPilot project status

Updated: 19 October 2026. Branch: feat/pdf-processing. The tested Vite/identity foundation is checkpointed in local Git. No remote/PR or public deployment exists.

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
