# Research completion handoff - 26 October 2026

Branch: feat/research-completion. Base: 9d4210a4e37a276b85d1cdc8d2257b1cc9d1a37e.

Implemented: writing, project, matrix-row and candidate-gap edit conflict review; named manuscript structures and outline navigation; matrix CSV/XLSX exports with provenance; verified publication-detail storage, previews and exports; bounded offline BibTeX/RIS import previews with researcher review. This does not complete every item in RELEASE_CHECKLIST.md.

Verification: 159 backend tests; 90 frontend tests; strict mypy; full backend Ruff; frontend lint, TypeScript and build all pass. The two new focused frontend cases cover matrix and gap conflict handling. Known backend test warnings concern Starlette transport deprecation and Alembic pgvector reflection. Vite warns about bundle size. Browser visual acceptance remains for the owner.

Tests ran in Compose project rp_completion_test, using isolated rp_greenfield_test PostgreSQL, separate Redis, temporary storage and no published ports, with image rp-completion-backend:dev. No application data, runtime or volumes were changed. No live provider calls were made.

Integration: review the diff against base before merging. Apply Alembic migrations 0016 and 0017 before starting the new backend, then rebuild web/API images. The health check derives its expected migration revision from the shipped Alembic tree. No new dependencies, secrets or environment variables are required. Generated OpenAPI and frontend API types are included. Preserve original sources and snapshots. Do not downgrade 0016 while matrix exports exist, or downgrade 0017 without accepting metadata loss. No such downgrade was performed.

Known limitations and remaining product/release work: RELEASE_CHECKLIST.md. Password recovery requires real email settings; metering requires a budget policy; retention/purge requires a retention decision. Current bibliography output remains a limited preview. DOI metadata lookup, historical reader/source replacement, writing assistance, synthesis, broader real-provider evaluation and deployment/restore acceptance remain unfinished.

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
- backend/app/modules/references/imports.py
- backend/app/modules/references/models.py
- backend/app/modules/references/router.py
- backend/app/modules/references/schemas.py
- backend/app/modules/references/service.py
- backend/tests/test_citation_formatting.py
- backend/tests/test_exports.py
- backend/tests/test_references.py
- docs/COMPLETION_HANDOFF.md
- docs/RELEASE_CHECKLIST.md
- docs/ROADMAP.md
- docs/learning/13-reference-manager.md
- docs/learning/01-research-projects.md
- docs/learning/14-writing-drafts.md
- docs/learning/15-export-snapshots.md
- docs/learning/11-literature-matrix.md
- docs/learning/12-candidate-gaps.md
- docs/openapi.json
- frontend/src/features/exports/exports-page.tsx
- frontend/src/features/references/references-page.tsx
- frontend/src/features/projects/project-conflict-review.tsx
- frontend/src/features/projects/project-form.tsx
- frontend/src/features/matrix/matrix-page.tsx
- frontend/src/features/gaps/gaps-page.tsx
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
- frontend/tests/projects.test.tsx
- frontend/tests/matrix.test.tsx
- frontend/tests/gaps.test.tsx
- frontend/tests/writing.test.tsx

## Matrix and gap conflict review phase

Added after the earlier handoff snapshot: `frontend/src/features/matrix/matrix-page.tsx`, `frontend/src/features/gaps/gaps-page.tsx`, `frontend/tests/matrix.test.tsx`, `frontend/tests/gaps.test.tsx`, the matrix/gap learning docs, and roadmap, release checklist, status and handoff updates. Final frontend checks for this phase: lint, typecheck, 90 tests across 21 files, and production build passed. The build reports the existing large JavaScript chunk warning. Backend code was unchanged; its previously verified 159 tests, Ruff and strict mypy remain applicable.

The isolated review application is running at http://localhost:3101/login and API readiness returned HTTP 200. Provider calls remain disabled. The shared app/runtime was not changed.
