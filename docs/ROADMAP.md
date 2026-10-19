# Focused implementation backlog

1. Completed: approved React/TypeScript/Vite migration, archived Next scaffold, real account foundation and generated API types; review all twelve user reference images.
2. Account UI accepted by user. Password recovery is explicitly deferred; implement real reset email/token expiry/revocation before public release, and settle the token-lifecycle requirement separately.
3. Completed: owner-scoped project create/read/edit, archive/restore, confirmed soft removal, questions/objectives, cursor lists, real dashboard and transactional activity. User visual acceptance of this new slice is next.
4. Completed: private immutable PDF storage, scoped duplicates/quotas, durable jobs/outbox, bounded PDF validation/page-linked extraction, retries/recovery and source-text review. Explicit replacement/version-history UI remains pending; preserve immutable source/extractor identity when implementing retrieval. Extracted sources are not yet embedded/indexed.
5. Source reader completed: actual PDF display, readable/raw text, measured passage highlights and version-checked links. Next — version-aware chunking, Google-hosted embeddings and Research Chat with an independently configured answer model: one configured provider, source-scoped retrieval, citations, streaming, abstention and repeatable RAG evaluation.
6. Literature matrix and candidate gaps: editable extracted fields, retained provenance and bounded claims.
7. Writing, references and exports: structured editor, revisions, citation management and actual DOCX/CSV/XLSX capability.
8. Release hardening: production identity policy, metering/budgets, security tests, observability, restore drill and deployment.

Use `REFERENCE_IMAGE_REVIEW.md` for the appropriate visual references in each slice. Do not expose unimplemented modules as functioning controls or copy third-party product claims from the screenshots.

## Deferred follow-ups agreed with the user — 19 October 2026

Continue the research feature phases now. Revisit these items earlier if a dependent feature requires them, otherwise during release hardening before public release:

- Edit conflicts: preserve unsaved input; compare the user's changes with latest saved fields; offer review/reapply or loading the latest version. Consider automatic merging only for non-overlapping field changes; recheck revisions on final save. Existing stale-write rejection remains in place. No collaborative editor is required for personal project settings.
- Removal lifecycle: design Trash/restore, a clearly communicated retention window, confirmed permanent deletion, and an idempotent purge job covering originals, versions, extracted evidence, embeddings and database rows. Coordinate processing cancellation and retries; document backup expiration separately. The proposed 30-day window is a recommendation, not an adopted retention policy. Current soft removal retains data and hides access; no recovery/purge UI exists yet.

While implementing ingestion, preserve the ability to cancel processing and clean up derived artifacts later. Deferral does not authorize automatic purging of current user data.
