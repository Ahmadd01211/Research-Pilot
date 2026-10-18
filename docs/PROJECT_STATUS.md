# ResearchPilot project status

Updated: 18 October 2026. Branch: feat/research-projects. The tested Vite/identity foundation is checkpointed in local Git. No remote/PR or public deployment exists.

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

Next research feature: private PDF library, storage/validation, versions/duplicate handling and durable ingestion, then embeddings/RAG. No document processing, AI inference or manuscript generation is implemented yet.

Soft deletion is retention, not a backup or a permanent erasure policy. Removed-project recovery/purge UI is not implemented. Production trusted-proxy abuse controls, account verification, backup/restore, dependency/container hardening and metering remain tracked in SECURITY.md.

Test smoke used synthetic development accounts; only its own synthetic project was soft-removed. No real user project, uploaded document, application Docker volume, design reference or old D: application was deleted or changed by test setup.
