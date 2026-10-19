# Identity security baseline and limits

Implemented in this foundation: Argon2id hashes, generic credential failure, random opaque sessions stored as hashes, absolute/idle expiry, rotation on login, revocation on logout, HttpOnly/SameSite cookies, production Secure-cookie/HTTPS configuration checks, Origin/CSRF checks, user-bound profile access, rate counters and private API-secret configuration. Frontend session state is in memory, not localStorage.

Built Nginx runs unprivileged, limits request bodies and supplies same-origin CSP/frame/content-type/referrer/permission headers. The local API is loopback-only; PostgreSQL and Redis have no host ports. Generated local database credentials are ignored by Git and were not printed. No paid AI provider or real research documents are connected.

Verified foundation and projects: sixteen PostgreSQL/Redis-backed tests; sixteen frontend component/client/schema tests; the built-app HTTP registration/login/profile/logout flow, CSRF/origin denial and revoked-cookie replay denial. No browser screenshot automation. One upstream Starlette TestClient/httpx deprecation warning remains; migrate the test transport deliberately during a dependency update.

Before public deployment: implement password reset and verified email delivery, define account verification/recovery and session management policies, decide whether the newer access/refresh-token requirement replaces opaque sessions, test the production Secure-cookie configuration end to end, establish trusted-proxy/client-IP handling and production abuse limits, add retention/backup/restore procedures, pin/scan container images, scan Python dependencies, and review the full deployment threat model.

The current backend IP bucket sees the API peer behind a reverse proxy, so it is a conservative shared bound rather than a reliable per-end-user-IP policy. Email-keyed login limits are separate. Resolve trusted forwarding/edge limits before multi-user public exposure; never trust arbitrary client-supplied forwarding headers.

The npm runtime dependency audit reported zero vulnerabilities at the time of this check. This is not a comprehensive security audit. Development cookies intentionally do not use Secure on local HTTP; never carry that setting into production.


## Project authorization and mutation safety

Owner ID is derived from the authenticated session, never a request body. Lists/details/activity are scoped; foreign IDs return 404 on every operation. Existing CSRF/origin enforcement covers PATCH/POST/DELETE. Archived projects are read-only on the server, stale revisions fail, and soft-removed records are excluded from normal queries. All fields are bounded, unknown fields are rejected, and SQLAlchemy binds query parameters. Title removal confirmation is a UI safety step; backend authorization remains mandatory.

New tests cover cross-account access across all methods, repeated/concurrent creation, simultaneous stale edits and transaction rollback. Soft deletion retains records; it is not a production retention/erasure policy. Password recovery remains explicitly deferred with user authorization, and remains required before public release.

## Original PDF storage boundary (19 October 2026)

Uploads enforce current-user ownership/CSRF before streaming and recheck lifecycle under the project lock at finalization. 20 MiB files; 100 files/200 MiB per project. Filename never selects a path. UUID-addressed files live in an API-only Docker volume, outside static serving. Authenticated attachment downloads apply the same ownership rule. Missing originals/storage errors return safe 503 messages.

Content type and %PDF- screening do not establish parser validity or malware safety. The Stored state makes no extraction/indexing claim. Do not enable public release without bounded isolated parser validation, durable jobs/recovery, upload rate/time controls, account-wide quotas, coordinated file/database backups, reconciliation, object-storage policy and the previously tracked identity hardening. No automated deletion/reconciliation runs; orphan files/staging from crashes can accumulate. Soft project removal retains files. Downloading untrusted originals is an explicit user action; originals are never embedded inline.

## Processing extension — 19 October 2026

The prior storage-only validation boundary now includes strict pypdf validation in a Linux subprocess, checksum verification, 512 MiB address-space cap, CPU/wall timeout and page/text bounds. Worker originals mount is read-only. Child environment omits database/Redis settings. Evidence is plain text; no embedded PDF/HTML execution or OCR. Extracted text is untrusted source content, never a privileged instruction. SQLAlchemy API/worker engine exceptions hide SQL bind parameters; broader database/logging policy remains release work.

Subprocesses and resource limits do not constitute a complete malicious-code sandbox, malware scanner or network boundary. Stronger parser isolation, container/dependency maintenance, upload abuse controls and prior storage/identity/backup/purge work remain required before public release. Not all PDFs/layouts are supported. Original immutable sources and extractor identities must remain traceable when citations/version replacement are added.

Retry and evidence endpoints preserve owner/project checks and CSRF on mutations. Failed workers cannot publish after an expired/superseded lease. Removed projects cancel at claim/finalization; archiving may allow an already accepted extraction to complete. These checks support future purge coordination but do not implement permanent erasure or retention changes.

## Source reader boundary

PDF.js is pinned/self-hosted and receives only authenticated checksum-verified original bytes. Rendered canvas and plain React text expose no scripting/forms/action layer. XFA/WASM are disabled; the older explicit no-eval compatibility flag is retained, while strict CSP remains authoritative (installed PDF.js 6 no longer types that flag). No unsafe-eval, CDN or iframe permission was added. Only inert decoder fallbacks/fonts/CMaps are copied; the optional QuickJS evaluator is not served. Worker .mjs MIME is explicitly JavaScript with inherited security headers. Browser canvas/image bounds reduce resource pressure but are not a complete malicious-code sandbox. Keep renderer/parser dependencies maintained and retain original download/error alternatives.

Reader preparation uses existing ownership/CSRF/project locks and is allowed only for legacy extracted pages without layouts. Raw text and recurring margin words remain available; cleanup is heuristic and never a guarantee of semantic or scientific accuracy. Source/version/anchor mismatches disable highlights. Google-hosted embedding direction is recorded but no provider key/call is configured; no source text has left the machine through an AI provider in this milestone. Production data-use terms and previous release hardening remain relevant.


## Figure evidence milestone

Figure previews use owned, checksum-verified originals locally. No external image URL or vision API is used. Uncertain figure-page prose is withheld from retrieval preparation. Caption detection is heuristic, not an accuracy guarantee.

## Links and quality assessment

PDF links are passive: only HTTP(S), simple mailto and resolved local PDF destinations become navigation controls. Scripts, file/remote-file and unsupported actions are disabled, and malformed links do not execute. External navigation is explicit and uses no referrer/no opener. No linked content is ingested automatically. Quality gates are heuristic safeguards, not a correctness guarantee.
