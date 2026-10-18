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
