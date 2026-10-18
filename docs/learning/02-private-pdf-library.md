# Learning 02: how a private PDF reaches durable storage

This walkthrough covers actual code implemented on 19 October 2026. Open a project, choose **Open research library**, then **Upload PDF**. This slice stores original bytes; it does not extract text or run AI.

## Follow one request

1. `frontend/src/features/documents/library-page.tsx` checks the chosen filename, empty size and 20 MiB bound. These checks provide fast feedback. They cannot protect the server: a caller can bypass JavaScript.
2. `frontend/src/lib/api/client.ts` gets a CSRF token and sends the File directly as application/pdf. Cookies authenticate the user; the CSRF header guards a state-changing request. The request uses the same origin, so there is no need to expose tokens in localStorage or introduce permissive CORS.
3. `backend/app/modules/documents/router.py` receives the request after existing authentication/CSRF dependencies. It checks project access before reading bytes. It streams into a randomly named staging file, checks the server-side byte limit, updates a SHA-256 digest and screens the PDF signature. Nginx independently caps this specific route at 20 MiB. Other API routes retain the smaller body cap.
4. `service.store` locks the project and checks ownership/archive state again. Someone could have archived the project while the upload was arriving. The second check closes that race. Locking only during finalization avoids blocking normal project edits for the duration of a slow upload.
5. The service checks for the same hash **inside that project**. If found, it returns the existing document with duplicate=true and deletes only the new staging file. It does not create another activity entry. Hash identity means identical bytes, not semantically equivalent papers; a recompressed PDF can differ.
6. The service checks project quotas under the same lock. Without that lock, two simultaneous uploads could each see free space and collectively exceed the quota.
7. `storage.publish` moves the staged file to `papers/<generated UUID>.pdf`. The user filename never determines a filesystem path. This prevents traversal such as `../private-file`; the original name is retained only in metadata.
8. SQLAlchemy commits the document row and project activity in one transaction. TanStack Query refreshes the library and activity cache after success. The UI displays Stored, not Ready for AI.

## Why separate router, service, model and storage?

The router handles HTTP details: headers, streaming and responses. The service handles ownership, duplicate/quota rules and transactions. The SQLAlchemy model describes durable metadata and database constraints. LocalStorage handles file keys and publication. This separation makes rules reusable by later workers and allows an object-storage adapter without rewriting UI or business rules. The cost is a few more modules than a one-file demo.

## The database/file transaction problem

PostgreSQL can atomically commit metadata and activity. It cannot roll back a filesystem rename. We publish the original before committing metadata so a successful row normally points to an existing file. We fsync file bytes and the containing directory on Linux before acknowledging success.

If the database connection disappears during COMMIT, the server may have committed even though our caller saw an error. Deleting that file immediately could destroy a saved original. We retain published files on errors and document the need for reconciliation. This favors data preservation over automatic cleanup. Normal upload staging files are cleaned; process crashes can still leave abandoned staging files.

A named Docker volume survives container rebuild/recreation. It is **not a backup** and it is not mounted at a public web path. Production needs backups of the database and files, tested restores and a storage system suitable for multiple hosts. Never reset application volumes to make tests pass.

## Privacy on download

`service.owned` first resolves the project using current_user.id, then resolves the document within that project. Guessing a document UUID or changing the URL does not grant access. A foreign account receives 404, as does a removed project. The raw file path/hash is absent from public JSON.

The API sends originals as attachments with a safe encoded filename. This slice deliberately does not embed unvalidated PDFs in the application origin. Stored PDF bytes are untrusted, even if the filename and header look correct. Header screening does not validate PDF structure, remove malicious content, decrypt PDFs or perform OCR.

## Why no background task yet?

An upload is now independently testable. The next slice can add a durable PostgreSQL job plus an outbox dispatcher and isolated parser. Calling Celery directly after a database commit can lose work if Redis is unavailable between those actions. An outbox stores the intent to process alongside document/job metadata, so a dispatcher can retry later. Late acknowledgements alone do not provide exactly-once processing; workers must be idempotent and recover leases safely.

Parsing comes before embeddings. Extracted pages need stable provenance so future citations point to actual evidence. Embeddings then support retrieval; they do not replace original text. Scanned documents require OCR, which is outside the first text-PDF ingestion milestone. A stored paper must not appear as indexed until that work succeeds.

## What the automated checks prove

Integration tests use separate disposable PostgreSQL/Redis and temporary storage paths. They verify byte-for-byte download, renamed duplicates, concurrent retries, project scope, cross-account denial, archive/removal behavior, limits, missing files, failed transactions, safe storage errors and paginated reads. Migration metadata comparison checks the schema matches the models. The storage fixture intentionally has a PDF header without valid PDF internals: this verifies the honest Stored-only boundary, not successful parsing.

Frontend tests verify the raw File/CSRF request, duplicate feedback, refreshed semantic table/download link, empty-file rejection, archive restrictions and retry state. They do not substitute for your visual review.

## Manual exercise

1. Open an active project and its research library. Upload a small real PDF.
2. Refresh the page; it should remain in the table. Download it and confirm it matches the original.
3. Upload the same file again, including a renamed copy. Expect a duplicate notice and one row.
4. Try a non-PDF or a file larger than 20 MiB. Expect a clear rejection.
5. Archive the project. Existing downloads should work; uploads should be disabled. Restore it to allow uploads.
6. Check on a narrow screen and with keyboard navigation. The table scrolls horizontally to preserve real row/column relationships rather than collapsing evidence into ambiguous cards.

Do not expect chat, extraction, preview or AI processing from this slice. Those are the next implementation steps.
