# Research completion handoff - 25 October 2026

Branch: feat/research-completion. Base: 9d4210a4e37a276b85d1cdc8d2257b1cc9d1a37e.

Implemented: draft protection/conflict review; named manuscript structures and outline navigation; matrix CSV/XLSX exports with provenance; verified publication-detail storage, previews and exports. This branch includes draft-protection commit 8306bf1. It is not the completion of every item in RELEASE_CHECKLIST.md.

Verification: 156 backend tests; 85 frontend tests; strict mypy; changed backend Ruff; frontend lint, TypeScript and build all pass. Existing full-backend Ruff failures remain in documents/front_matter.py (F841) and documents/quality.py (B905), awaiting file-ownership approval. Known test warnings concern Starlette transport deprecation and Alembic pgvector reflection. Vite warns about bundle size. Browser visual acceptance remains for the owner.

Tests ran in Compose project rp_completion_test, using isolated rp_greenfield_test PostgreSQL, separate Redis, temporary storage and no published ports, with image rp-completion-backend:dev. No application data, runtime or volumes were changed. No live provider calls were made.

Integration: review the diff against base before merging. Apply Alembic migrations 0016 and 0017 before starting the new backend, then rebuild web/API images. The health check derives its expected migration revision from the shipped Alembic tree. No new dependencies, secrets or environment variables are required. Generated OpenAPI and frontend API types are included. Preserve original sources and snapshots. Do not downgrade 0016 while matrix exports exist, or downgrade 0017 without accepting metadata loss. No such downgrade was performed.

Known limitations and remaining product/release work: RELEASE_CHECKLIST.md. Password recovery requires real email settings; metering requires a budget policy; retention/purge requires a retention decision. Current bibliography output remains a limited preview. Reference import, historical reader/source replacement, writing assistance, synthesis, broader real-provider evaluation and deployment/restore acceptance remain unfinished.

## Exact changed files against base

- PROJECT_STATUS.md
- backend/alembic/versions/0016_matrix_exports.py
- backend/alembic/versions/0017_reference_details.py
- backend/app/main.py
- backend/app/modules/exports/matrix_snapshot.py
- backend/app/modules/exports/models.py
- backend/app/modules/exports/schemas.py
- backend/app/modules/exports/service.py
- backend/app/modules/references/formatting.py
- backend/app/modules/references/models.py
- backend/app/modules/references/schemas.py
- backend/app/modules/references/service.py
- backend/tests/test_citation_formatting.py
- backend/tests/test_exports.py
- backend/tests/test_references.py
- docs/COMPLETION_HANDOFF.md
- docs/RELEASE_CHECKLIST.md
- docs/ROADMAP.md
- docs/learning/13-reference-manager.md
- docs/learning/14-writing-drafts.md
- docs/learning/15-export-snapshots.md
- docs/openapi.json
- frontend/src/features/exports/exports-page.tsx
- frontend/src/features/references/references-page.tsx
- frontend/src/features/writing/draft-conflict-review.tsx
- frontend/src/features/writing/draft-navigation-guard.tsx
- frontend/src/features/writing/draft-starter.tsx
- frontend/src/features/writing/use-draft-protection.ts
- frontend/src/features/writing/writing-page.tsx
- frontend/src/lib/api/schema.d.ts
- frontend/src/main.tsx
- frontend/src/styles/globals.css
- frontend/tests/draft-protection-state.test.ts
- frontend/tests/draft-protection.test.tsx
- frontend/tests/draft-starter.test.tsx
- frontend/tests/exports.test.tsx
- frontend/tests/references.test.tsx
- frontend/tests/writing.test.tsx
