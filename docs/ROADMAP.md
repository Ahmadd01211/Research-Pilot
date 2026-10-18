# Focused implementation backlog

1. Completed: approved React/TypeScript/Vite migration, archived Next scaffold, real account foundation and generated API types; review all twelve user reference images.
2. Account UI accepted by user. Password recovery is explicitly deferred; implement real reset email/token expiry/revocation before public release, and settle the token-lifecycle requirement separately.
3. Completed: owner-scoped project create/read/edit, archive/restore, confirmed soft removal, questions/objectives, cursor lists, real dashboard and transactional activity. User visual acceptance of this new slice is next.
4. Completed first library slice: private immutable PDF storage, project-scoped duplicates, quotas, paginated table and authenticated downloads. Next: versions, bounded isolated parser validation/text extraction, durable jobs/outbox and recovery. Stored originals are not yet parsed or indexed.
5. Embeddings and Research Chat: one configured provider, source-scoped retrieval, citations, streaming, abstention and repeatable RAG evaluation.
6. Literature matrix and candidate gaps: editable extracted fields, retained provenance and bounded claims.
7. Writing, references and exports: structured editor, revisions, citation management and actual DOCX/CSV/XLSX capability.
8. Release hardening: production identity policy, metering/budgets, security tests, observability, restore drill and deployment.

Use `REFERENCE_IMAGE_REVIEW.md` for the appropriate visual references in each slice. Do not expose unimplemented modules as functioning controls or copy third-party product claims from the screenshots.
