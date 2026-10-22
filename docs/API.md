# Identity API contract

## Evidence search (current)

The checked OpenAPI schema includes owner-scoped `GET /api/v1/projects/{project_id}/evidence/capabilities` (whether hosted indexing is configured), `GET .../evidence/indexes` (current index states), and `POST .../evidence/search` (question, selected document IDs, bounded result count). `POST /api/v1/projects/{project_id}/documents/{document_id}/index` explicitly queues eligible source chunks for a hosted embedding provider; the matching GET returns job progress. Indexing is disabled by default. Search returns page-linked source chunks, not a generated answer. State-changing calls require session, Origin and CSRF checks. Foreign or removed projects return 404.

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

## Processing extension (migration 0004; supersedes Stored-only status above)

DocumentRead now includes status plus processing state, total attempts, safe error_code, page_count, extractor_version and completed_at. No lease token, broker details or filesystem key is exposed. New uploads queue processing in the same metadata transaction; duplicate uploads return the existing state without new work. Existing retained files are backfilled into queued jobs.

- POST `/api/v1/projects/{project_id}/documents/{document_id}/retry`: session/Origin/CSRF required; owned non-archived project. Only failed temporary storage/worker outcomes with fewer than five total attempts can queue another attempt. Other states/outcomes return 409; foreign/removed resources return 404. No body required.
- GET `.../documents/{document_id}/pages/{page_number}`: owned extracted document only; returns physical page_number, plain text, source_sha256 and extractor_version. Not yet extracted → 409; missing/out-of-range page → 404. Empty pages remain explicit. Download remains an authenticated attachment.

States: queued → processing → extracted / failed / queued (temporary retry); removed projects cancel at claim/publication. Text extracted does not mean indexed, scientifically correct, OCR-complete or RAG-ready. Valid input supports 1–300 physical pages and bounded text; malformed/encrypted/insufficient text/resource/time/integrity errors are explained by the library. Automatic recovery stops at three attempts; user retries stop at five total.

## Source reader (migration 0005)

EvidencePage includes nullable layout: version, rotated CropBox width/height/rotation, measured words (text, normalized top-left box, margin flag), readable passages (deterministic id/text/word_indices) and excluded_margin_text. Raw `text`, source_sha256 and extractor_version remain separate. No guessed coordinates or model-generated source text is returned.

POST `.../documents/{id}/prepare-reader`: owned live non-archived project, Origin/CSRF required, no body. Only an extracted document missing layouts can queue the bounded upgrade; pending/already-prepared/other outcomes return 409. No automatic backfill processing on migration. Metadata returns normal queued processing state; pages become available again on successful completion. Original attachments are unchanged. Current layout identity is word-passages-v3 plus pdfplumber/pdfminer versions.

Frontend evidence links identify page, passage ID, original source checksum and reader version. These are source anchors for future RAG citations; the reader itself does not generate or verify scientific claims.

Evidence layouts now include tables (box, detection method, rows of anchored cells) and reader_current. prepare-reader also accepts an extracted document with an older reader version, while rejecting already-current/pending work. Cell indices are validated like prose passages. No database migration is needed for the additive JSON layout fields.


## Figure evidence milestone

Owned GET /api/v1/projects/{project_id}/documents/{document_id}/figures returns source captions, crop/page fallback, source identity and explicit author-discussion anchors; foreign/removed resources are hidden. Figures require completed extraction.

## Links and quality assessment

Owned GET /api/v1/projects/{project_id}/documents/{document_id}/quality returns current source/reader/quality identity, per-page findings, checked/review/blocked/unassessed page counts and actual retained-link count. EvidencePage layout includes links and quality. Foreign/removed resources are hidden; incomplete extraction returns 409.
