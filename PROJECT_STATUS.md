# ResearchPilot project status

Updated: 19 October 2026. Branch: feat/pdf-library. The tested Vite/identity foundation is checkpointed in local Git. No remote/PR or public deployment exists.

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

Private original PDF storage is now implemented; details below. Next: durable ingestion, isolated parser validation/text extraction, explicit versions/retries/recovery, then embeddings/RAG. No PDF parsing, AI inference or manuscript generation is implemented yet.

Soft deletion is retention, not a backup or a permanent erasure policy. Removed-project recovery/purge UI is not implemented. Production trusted-proxy abuse controls, account verification, backup/restore, dependency/container hardening and metering remain tracked in SECURITY.md.

Test smoke used synthetic development accounts; only its own synthetic project was soft-removed. No real user project, uploaded document, application Docker volume, design reference or old D: application was deleted or changed by test setup.


## Private PDF storage slice — 19 October 2026

Project detail → Open research library → Upload PDF. The real library includes a semantic paginated table, actual counts, empty/loading/error/success states, private original download and duplicate notices. Archived projects are readable but reject uploads; removed/foreign projects hide document endpoints. Generated contract includes the raw binary PDF request.

Upload screening: 20 MiB maximum, bounded filename, content type and PDF signature. This is **not parser validation**. Immutable originals use UUID filenames in a private named Docker volume; checksums deduplicate within the project. Finalization rechecks lifecycle/ownership and locks the project to serialize quotas and concurrent retries. Per-project limit: 100 papers or 200 MiB. Stored is the only processing status; no extraction, indexing, OCR or RAG readiness is claimed. Revisions/versions and durable worker jobs remain next.

Verification: backend Ruff and strict mypy passed (29 source files); all 24 isolated PostgreSQL/Redis integration tests passed, including eight document cases, concurrency, safe storage errors and migration parity. Frontend lint/typecheck, all 20 tests and local/container production builds passed. Built-app HTTP smoke passed through Nginx with a >256 KiB synthetic PDF fixture, exact download bytes, list and renamed duplicate. Migration 0003 applied additively. Existing account/project data and Docker volumes were preserved. One upstream Starlette/httpx warning remains. User visual acceptance of the library remains pending; no screenshot automation used.

Read learning/02-private-pdf-library.md and ADR 0004 for actual code flow and tradeoffs. Staging cleanup covers normal request outcomes; crashes may leave staging files. Published files are retained on ambiguous commit failures to avoid loss; orphan reconciliation, coordinated backups, production object storage, upload abuse/time limits and full PDF validation remain release work. The smoke created one synthetic development account/project/original and retained it; it did not alter real user documents.
