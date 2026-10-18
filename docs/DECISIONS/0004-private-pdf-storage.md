# ADR 0004 — Private original PDF storage

19 October 2026. Accepted implementation boundary: storage first, durable ingestion next.

The project library accepts raw application/pdf bodies through an authenticated, CSRF-protected endpoint. Filename is a bounded query parameter used only as display/download metadata. Raw streaming avoids multipart spooling before authentication and avoids adding a multipart dependency. This API is less familiar to generic form clients than multipart; OpenAPI explicitly documents the binary request body.

Each upload is bounded to 20 MiB and must start with the PDF signature. This is format screening, **not parser validation or malware scanning**. Originals download as attachments and are never rendered inline. Stored is the only current state. No queued, parsed, indexed, version history, evidence preview or RAG readiness is claimed. Malformed/encrypted/scanned files may be stored now and must receive honest validation/extraction outcomes when ingestion is added.

Project limits are 100 originals and 200 MiB. Ownership is enforced in SQL for list, upload, metadata and download. Before receiving bytes the service checks ownership; after receiving bytes it locks and rechecks the project. Archive/delete transactions use the same row lock. Archives allow reads/downloads and deny uploads. Soft-removed projects hide all document endpoints while retaining files.

Originals are immutable UUID-addressed files, separate from display filenames. SHA-256 plus a unique(project_id, sha256) constraint detects byte-identical papers within one project. The project row lock serializes concurrent finalization, quota checks and lifecycle changes. It is never held during network upload. The same file in a different project gets its own original; this avoids account-wide hash discovery. A changed file is a separate document until explicit version/replacement semantics are implemented.

LocalStorage uses an API-only Docker volume with an appuser-owned root and no public static URL. Publication uses fsync plus atomic rename on the same Linux filesystem, before committing metadata and activity together. Normal staging files are removed in finally blocks. A crash can leave staging files, and a database failure after publication can leave an orphan. Ambiguous COMMIT outcomes retain bytes because deleting a potentially committed original is worse than retaining an orphan. No automatic purge is implemented. A future reconciler must use age thresholds and active-upload coordination; never blindly delete files absent from a possibly stale database snapshot.

Local storage suits this development deployment, not multiple application hosts. S3-compatible storage, coordinated database/file backups, reconciliation, upload timeouts/rate limits and account-wide quotas remain release work. Filesystem and PostgreSQL cannot share one atomic transaction. Storage errors return safe 503 responses without filesystem paths. Download responses use no-store, nosniff and attachment disposition.

Next: durable job/outbox, bounded isolated parsing, page-level provenance, versions, extraction failures/retries/recovery; then configured embeddings and source-scoped RAG. No worker is scheduled by this slice.
