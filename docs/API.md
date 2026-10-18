# Identity API contract

The checked contract is `openapi.json`; the frontend types are generated into `frontend/src/lib/api/schema.d.ts`. Generate the public schema with `backend/scripts/export_openapi.py` in the backend container, without connecting to a database, then run `npm run api:generate` in frontend. CI compares regenerated artifacts for drift.

| Method | Path | Behavior |
|---|---|---|
| GET | /api/v1/auth/csrf | Set/reuse HttpOnly CSRF cookie and return the token for a matching request header |
| POST | /api/v1/auth/register | Validate and create an account; 201 success; 409 conflict; does not create a session |
| POST | /api/v1/auth/login | Verify credentials, rotate existing session and issue new session/CSRF cookies |
| POST | /api/v1/auth/logout | Revoke current session and clear cookies; 204 |
| GET | /api/v1/me | Return only the authenticated user's public profile |
| PATCH | /api/v1/me | Update only the current user's display name |
| GET | /api/v1/health/live | Process liveness |
| GET | /api/v1/health/ready | PostgreSQL, migration identity/session schema and Redis readiness |

State-changing operations require the configured Origin and matching CSRF cookie/header; authenticated changes also validate the token hash against the session. Browser routes use relative URLs through the same-origin proxy. Login failures are generic. Validation errors do not echo submitted password fields; infrastructure errors use safe structured responses.

Registration redirects to sign-in after success rather than chaining registration and login into a potentially misleading single operation. Profile edits show unsaved, saving, success and failure feedback. Database-backed identity tests and the built-frontend HTTP smoke verify cookie and persistence behavior; browser visual acceptance remains manual.


## Research projects — implemented

| Method | Path | Contract |
|---|---|---|
| GET | /api/v1/projects | Owned nondeleted projects; status=active/archived/all; literal title search; limit 1–50; cursor; items/next_cursor/total |
| POST | /api/v1/projects | title, description, research_questions[], objectives[], request_id UUID; idempotent within owner; 201 |
| GET | /api/v1/projects/{id} | Owned nondeleted project with revision and lifecycle timestamps |
| PATCH | /api/v1/projects/{id} | expected_revision plus at least one editable field; no explicit null; 409 on archive/conflict |
| POST | /api/v1/projects/{id}/archive | expected_revision; preserve data, prohibit edits |
| POST | /api/v1/projects/{id}/restore | expected_revision; restore an archived project |
| DELETE | /api/v1/projects/{id} | JSON expected_revision; 204; confirmed soft removal, no physical purge |
| GET | /api/v1/projects/{id}/activity | Owner-scoped paginated changes; items/next_cursor |

All mutations reuse session/Origin/CSRF protection. Ownership is never accepted from input. Same creation key/same payload returns the existing project; changed payload or a removed project returns 409. Stale edits return 409 without changing data. Edit responses explicitly require the fields the frontend consumes. Project/activity creation and changes commit atomically.

The web proxy request limit is 256 KiB to accommodate valid bounded project metadata. This is not a PDF upload allowance; the future document endpoint needs its own validated limits and processing pipeline.

## Private PDF library (migration 0003)

- GET `/api/v1/projects/{project_id}/documents?offset=0&limit=25`: owned page, limit 1–50, offset 0–100, actual total.
- POST same collection with `?filename=Original.pdf`: raw application/pdf body, session/Origin/CSRF required, ≤20 MiB, PDF signature screening. 200 returns `{document, duplicate}` for both newly stored and duplicate originals. Identical bytes reuse the project document; no cross-project hash discovery. 413 too large, 415 wrong content type, 422 invalid name/signature, 409 archive/quota, 404 inaccessible project.
- GET `.../documents/{document_id}`: owned metadata; status is Stored only. No storage keys/checksums exposed.
- GET `.../documents/{document_id}/download`: authenticated attachment; safe 503 if original unavailable. Removed projects return 404; archives allow read/download.

No parsing, replacement, deletion, processing retry or evidence-preview endpoint is implemented in this storage slice. Never interpret signature screening as structural PDF validation.
