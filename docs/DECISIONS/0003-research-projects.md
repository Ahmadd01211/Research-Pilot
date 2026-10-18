# ADR 0003 — owner-scoped research projects

Status: accepted implementation within the user-authorized next phase, 18 October 2026.

Use an explicit projects module (router, schemas, service, models) with no generic repository hierarchy. The authenticated identity supplies the owner ID. Owned-resource queries include owner and project ID together, and return 404 for foreign/missing resources.

Research questions/objectives are bounded JSONB arrays because they currently have one project-form lifecycle. Normalize them when they need stable evidence links, independent history or permissions. Add project/activity tables with Alembic revision 0002; preserve the existing identity schema and data.

Use creation request UUIDs scoped to owner plus a normalized payload fingerprint. A unique database constraint makes retry protection hold under concurrency. Reusing a key with changed data returns conflict. Replaying creation after removal cannot resurrect a project.

Use expected revisions for edits/lifecycle operations and a short row lock to make check-and-write atomic. Return 409 on stale revisions and retain the user's form text. Commit activity in the same transaction as project changes; do not call AI or external services while holding this lock.

Archive is read-only and reversible. Removal uses a typed-title confirmation and a soft-delete timestamp, excludes the project from ordinary reads, and does not purge files or cascade-delete future evidence. Repeated DELETE does not duplicate activity. No removed-project recovery or permanent purge interface is implemented yet; define retention and erasure semantics before public release.

Lists use bounded cursor pagination ordered by creation time and UUID. Literal title search escapes LIKE wildcards. TanStack Query owns server data; React Hook Form owns drafts. Project CRUD stays synchronous in the API because it is short database work; workers are reserved for actual document/AI/export workloads.

Tradeoffs: cursor pagination favors sequential browsing over page-number jumps; row locks may briefly queue concurrent updates; soft deletion retains storage and creates retention obligations; JSONB is deliberately simple for bounded text lists. These choices should be revisited when concrete lifecycle or measured performance needs change.
