# ResearchPilot

Greenfield academic research workspace. The active frontend is React + strict TypeScript + Vite. The app implements identity and research projects. PDF/RAG and the other research modules remain planned, not simulated. The separate design export contains clearly labeled synthetic examples.

## Local development

Prerequisites: Docker Desktop with Linux containers, Node.js 24 LTS and Git. The frontend uses React/TypeScript/Vite; the built app is served by Nginx. Use `localhost` consistently (not 127.0.0.1) for the browser origin.

1. Copy `.env.example` to `.env`, replacing its password with a random local value.
2. `docker compose up --build -d`
3. Open http://localhost:3100/register. API OpenAPI: http://localhost:8100/docs.
4. Register with a synthetic email and a password of at least 12 characters, edit your profile, reload and sign out.

Ports and named volumes are independent of the old application. PostgreSQL and Redis have no host ports. Stop services with `docker compose stop`. Never remove application volumes to fix a migration.

## Verify

The old Next.js frontend is archived in `docs/archives/frontend-nextjs-before-vite.zip`. Reference-image decisions are in `docs/REFERENCE_IMAGE_REVIEW.md`.

From `frontend`: `npm ci`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`.

From the repository root: `docker compose -f compose.test.yaml build tests`, then `docker compose -f compose.test.yaml run --rm --no-deps tests ruff check .`, `docker compose -f compose.test.yaml run --rm --no-deps tests mypy`, and `docker compose -f compose.test.yaml up --abort-on-container-exit --exit-code-from tests`. Stop/remove only those disposable services with `docker compose -f compose.test.yaml down`.

Tests accept only the explicitly named test database. Development data is never truncated by tests. The user performs visual UI acceptance manually.

## Dependency maintenance

Frontend uses `package-lock.json` and `npm ci`; backend uses generated `requirements.lock`. Compile backend requirements with pip-tools on Python 3.12; review upgrades and rerun all checks. Container base-image tags must be pinned and scanned before a production deployment. No production deployment or paid AI calls are configured.

Read `PROJECT_STATUS.md` for verified behavior and remaining gaps.

For the backend code walkthrough, read `docs/learning/01-research-projects.md`. Repeat local project HTTP checks with `python scripts/smoke_projects.py` (synthetic local accounts only).
