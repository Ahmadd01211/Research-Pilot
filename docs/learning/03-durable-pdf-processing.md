# Learning 03: reliable PDF processing before RAG

This lesson describes the implementation, not a hypothetical architecture. Start in the project library: upload a text PDF, watch Queued → Extracting text → Text extracted, then open Review extracted text. Failed files show an explanation. An accepted PDF signature is still not proof of valid PDF structure.

## The end-to-end path

`documents/service.py` creates Document and its DocumentJob relationship before committing. SQLAlchemy orders the dependent inserts. PostgreSQL either saves the original metadata, processing intent and upload activity together, or rolls them back. No request waits for PDF parsing.

`workers/dispatcher.py` runs as a separate Compose service and calls `processing.dispatch_once`. The query locks eligible rows with `FOR UPDATE SKIP LOCKED`. A second dispatcher skips already claimed rows. It publishes only document UUIDs to Celery, never original text or credentials. After publishing it advances dispatch_after. Publishing failure rolls the transaction back, preserving pending intent.

Why not call `.delay()` directly in the upload route? Database and Redis cannot participate in one transaction here. A crash after saving metadata but before publishing could otherwise strand the upload. Why not mark a publish as permanently sent? Redis might lose that message before a worker starts. We republish still-queued rows; claiming is idempotent.

## A lease is temporary permission to publish a result

`processing.claim` locks the project then the job. It accepts only Queued work, checks project removal, increments attempts and assigns a random lease_token. Competing workers cannot both claim the same queued row. The transaction commits immediately; parsing happens afterward without holding locks.

`processing.finish` locks in the same order and verifies state, token and deadline. A result from an expired or superseded attempt is discarded. This is fencing: a stale worker cannot overwrite the current attempt. The dispatcher recovers expired leases if a worker crashed before finish.

The lease lasts 240 seconds, longer than the 150-second Celery hard limit. This avoids treating normal parsing as abandoned while it is still allowed to run. A database/broker outage can delay recovery; the system keeps visible pending state instead of inventing success. Late message acknowledgement helps redelivery but is not a substitute for database claims and fencing.

## Why use a parser subprocess?

PDFs contain compressed streams and complicated structures. Small upload size does not bound decompressed memory use. `extraction.py` first verifies SHA-256, then starts `python -m app.modules.documents.parse_pdf` with a minimal environment. The child applies Linux resource limits before importing pypdf. The worker waits at most 60 seconds, after which subprocess.run kills/waits for the child.

Limits are explicit: 512 MiB address space, 40/45 seconds CPU, 300 pages, 100k characters per page, 2m per document. The child returns bounded JSON, not database writes. The parent checks the shape again. The worker's shared originals volume is read-only. The advantage is predictable failure and protection from ordinary resource exhaustion. The cost is process startup and rejecting some complex PDFs. This is not a complete security sandbox: production still needs stronger isolation and maintenance.

## Failure categories are product behavior

- encrypted_pdf: upload an unlocked copy you are permitted to use; no passwords are collected.
- invalid_pdf: structure could not be parsed strictly; a fresh export may help.
- insufficient_text: fewer than 40 readable characters; this may be scanned, blank, or image-only. We do not pretend to have OCR.
- page_limit, resource_limit, parser_timeout: the document exceeded supported processing limits.
- integrity_mismatch: original bytes no longer match their saved checksum; operator restoration is needed. Re-upload duplicate handling is not a storage-repair mechanism.
- storage_unavailable or worker_failure: temporary operational problems can be retried, with a hard attempt budget.

Automatic work stops at three total attempts. Eligible user retries allow at most five total attempts. The backend enforces this even if the UI is bypassed. Repeated retries of deterministic failures would add cost without changing the input. No fake progress percentage is displayed.

## Evidence must keep its source identity

Each DocumentPageText row stores document_id, physical PDF page_number and plain text. A successful transaction saves all pages, page count, extractor version, completion time, Extracted status and one activity event together. A failed transaction exposes no partial set of pages. Repeated task delivery cannot duplicate pages or activity.

Evidence endpoints run the same owned-project check as downloads. Responses include the original-file checksum and extractor version (`pypdf-<version>:page-text-v1`). This identifies the exact immutable input and extraction algorithm. PDF page 1 means the first physical page, not necessarily the printed label “1.” Source text is rendered as React text in a pre element, preventing HTML interpretation. It is not an AI summary.

Tables, columns, mathematics, headers and reading order can be imperfect even after successful extraction. The preview includes a warning and original download action so you can verify important quotations. Some pages can be blank while the overall paper has usable text. Existing originals are not silently replaced; replacement/version-history UI is still separate work.

## What changes in the UI?

TanStack Query polls the visible library page every three seconds only while it contains queued/processing papers. Once processing reaches terminal outcomes, polling stops. Success exposes a review link; eligible failures expose retry; deterministic failures explain the next action. Page navigation requests one source page at a time and retains column relationships in the library's semantic table.

## How this prepares RAG

We now have source-linked text. Next, a version-aware chunker can split it while preserving document/page identity. Embeddings encode passages for retrieval. Research Chat must restrict retrieval to the current user's selected sources and cite actual retrieved passages. Extracted alone does not mean indexed or answerable. No embedding provider is called in this phase, and no keys or billing decision is needed yet.

## Verification and manual exercise

Backend tests cover real valid, encrypted, malformed and blank PDFs; page provenance; concurrent claims; lost-publication redelivery; expired leases; stale results; bounded retries; ownership/CSRF; cancellation; atomic page rollback; original integrity and parser timeout. Isolated test databases and temporary file roots protect real user data. The full-app smoke additionally exercises the actual dispatcher, Redis, Celery worker, subprocess parser, database and Nginx through HTTP.

Try a small text PDF, wait for extraction, inspect two pages and compare the original. Try an image-only or encrypted PDF and read its explanation. Refresh during processing and confirm the state survives. Archive a project and confirm new uploads/retries are disabled while accepted extraction/downloads remain available. No browser screenshot automation is used; visual acceptance is yours.

Deferred conflict-resolution and Trash/retention/purge improvements remain recorded in ROADMAP.md. This phase checks removal at claim and result publication so future erasure work has a safe foundation; it does not implement permanent deletion or a retention policy.
