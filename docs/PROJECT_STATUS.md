# ResearchPilot project status

Updated: 18 October 2026.

## Active application

React + strict TypeScript + Vite frontend; React Router; FastAPI modular backend; PostgreSQL/pgvector; Redis; independent Celery worker. The user approved replacing Next.js. Original frontend files are preserved in `docs/archives/frontend-nextjs-before-vite.zip`. Working branch: `feat/vite-foundation` (new local repository; no remote or PR created).

Open the real local app at **http://localhost:3100/register**. Active routes: home, registration, login, authenticated dashboard and profile. Real registration/login, persistent profile edits and revoking logout are implemented. There are no fake projects or AI usage numbers in the live account view.

## Verified this turn

- Frontend lint and strict TypeScript checks passed.
- Ten frontend schema/client/component tests passed.
- Vite production build passed locally and inside the Node 24 frontend image.
- Backend Ruff and strict mypy passed (18 source files).
- Eight real PostgreSQL/Redis-backed identity tests passed, including migration/model parity, hashing, expiry, rotation/revocation, CSRF/origin checks, rate limits and profile isolation.
- Built Nginx same-origin HTTP smoke passed: deep-route reload/security headers, API readiness, register/login, persistent profile update, CSRF/origin rejection and rejection of a replayed revoked cookie.
- npm runtime audit reported zero vulnerabilities.
- API, PostgreSQL, Redis, worker and built frontend reported healthy. This is not proof of future document-processing tasks.
- One upstream TestClient/httpx deprecation warning remains. Browser visual testing was not automated.

HTTP smoke created one synthetic development account with an ephemeral password; no real user credentials or research data were used or printed. Test services are isolated and stopped after verification; application volumes are preserved.

## Design and references

The responsive design preview remains separate at `design-export/` (http://localhost:3200 while its preview server runs). The user manually accepted its responsiveness and navigation. All twelve images in `frontend example layout` were inspected and left unchanged; see `docs/REFERENCE_IMAGE_REVIEW.md`.

The production app currently implements only the identity slice. The broader prototype remains a clearly labeled synthetic reference; it is not an AI or PDF backend.

## Deliberate limits / next work

Password reset, account verification, public-deployment abuse/retention policies and administrative session management remain unimplemented. The previous opaque HttpOnly-cookie session design is retained; the newer access/refresh-token wording needs a separate architecture decision before replacement. See `docs/SECURITY.md` for deployment limits, including trusted-proxy/client-IP behavior.

Next: user tests real registration → login → edit profile → reload → logout. Then complete the next identity requirements and owner-scoped projects, followed by library ingestion and RAG.

No old D: application was accessed, migrated or reused. Reference images and accepted design files were preserved. No application volumes, uploaded documents or user data were deleted.
