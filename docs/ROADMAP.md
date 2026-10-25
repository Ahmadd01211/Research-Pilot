# Focused implementation backlog

## Completion work in isolation - 25 October 2026

Branch feat/research-completion includes draft protection, named manuscript structures, matrix CSV/XLSX snapshots with provenance, and expanded verified publication details. These changes are not deployed to the shared runtime. See RELEASE_CHECKLIST.md for remaining work and required operational choices. Historical checkpoints below describe earlier implementations and can be stale.

## Latest completed slice

Matrix and gap editors now compare the saved revision with unsaved edits after a conflict, let the researcher keep the draft for a separate save or load the current record, and retain a retry path if the latest record cannot be loaded. Gap conflict review also refreshes eligible matrix evidence and excludes removed cells when resolving. Focused tests cover both paths. Automatic DOI metadata lookup and full interchange-format fidelity remain open.

Persistent Research Chat now stores project-scoped threads and immutable per-turn answer/source snapshots. Multi-turn context is limited to six prior turns and new claims still require citations from freshly retrieved evidence. Provider evaluation, budgets and metering remain next for this feature area.

1. Completed: approved React/TypeScript/Vite migration, archived Next scaffold, real account foundation and generated API types; review all twelve user reference images.
2. Account UI accepted by user. Password recovery is explicitly deferred; implement real reset email/token expiry/revocation before public release, and settle the token-lifecycle requirement separately.
3. Completed: owner-scoped project create/read/edit, archive/restore, confirmed soft removal, questions/objectives, cursor lists, real dashboard and transactional activity. User visual acceptance of this new slice is next.
4. Completed: private immutable PDF storage, scoped duplicates/quotas, durable jobs/outbox, bounded PDF validation/page-linked extraction, retries/recovery and source-text review. Explicit replacement/version-history UI remains pending; preserve immutable source/extractor identity when implementing retrieval. Extracted sources are not yet embedded/indexed.
5. Source reader completed: actual PDF display, readable/raw text, measured passage highlights and version-checked links. A first real-paper retrieval baseline measures gold chunk coverage and ranked results. Versioned Google-hosted embeddings, owner-scoped vector evidence search, and a single-turn cited Research Chat preview are implemented behind an opt-in server key; no key is configured and live provider retrieval/answers remain unverified. Next — broader repeatable real-provider RAG evaluation, persistent conversation history with per-turn provenance, budgets and metering.
6. Literature matrix and candidate gaps: source-linked, user-authored rows and field-level provenance; editable gap hypotheses with supporting/challenging matrix cells and derived uncertainty labels; revision-conflict review is implemented. Next: broader search coverage and optional AI suggestions after retrieval evaluation.
7. Writing, references and exports: researcher-verified records, limited APA/MLA/Chicago bibliography previews, versioned Markdown drafts, and immutable CSV/XLSX reference and Markdown/DOCX draft snapshots are implemented. Next: richer editing, complete citation metadata, and export retention.
8. Release hardening: production identity policy, metering/budgets, security tests, observability, restore drill and deployment.

Use `REFERENCE_IMAGE_REVIEW.md` for the appropriate visual references in each slice. Do not expose unimplemented modules as functioning controls or copy third-party product claims from the screenshots.

## Deferred follow-ups agreed with the user — 19 October 2026

Continue the research feature phases now. Revisit these items earlier if a dependent feature requires them, otherwise during release hardening before public release:

- Edit conflicts: preserve unsaved input; compare the user's changes with latest saved fields; offer review/reapply or loading the latest version. Consider automatic merging only for non-overlapping field changes; recheck revisions on final save. Existing stale-write rejection remains in place. No collaborative editor is required for personal project settings.
- Removal lifecycle: design Trash/restore, a clearly communicated retention window, confirmed permanent deletion, and an idempotent purge job covering originals, versions, extracted evidence, embeddings and database rows. Coordinate processing cancellation and retries; document backup expiration separately. The proposed 30-day window is a recommendation, not an adopted retention policy. Current soft removal retains data and hides access; no recovery/purge UI exists yet.

While implementing ingestion, preserve the ability to cancel processing and clean up derived artifacts later. Deferral does not authorize automatic purging of current user data.


## Figure evidence milestone

Completed figure source cards and typed chunk preparation. Next: Google embedding configuration, version-aware indexing and owned source-scoped retrieval; then cited Research Chat with figure cards and abstention. Complete historical source navigation, conflict reconciliation and Trash/purge remain pending.

## Links and quality assessment

Completed passive source links and per-page/document automatic evidence checks, with current-version gates and visible review states. Next: review unresolved-layout coverage, configure Google embeddings and implement version-scoped indexing/retrieval. No provider key, embedding request or answer generation was introduced.

## Completed: retrieval redundancy control — 22 October 2026
Search and Research Chat now retrieve a larger ranked candidate pool and suppress repeated same-source prose before choosing final evidence. Five-word overlap is conservative; changed numbers, independent papers and distinct table rows are preserved. No reindexing required. Eight related tests, Ruff and mypy passed. This completes the redundancy-control slice; broader real-provider recall evaluation and metering remain pending.

## Completed: offline retrieval evaluation gate — 22 October 2026
The existing PDF/case/prediction evaluator now fails on missing gold evidence, stale prediction IDs, duplicate predictions, recall below 0.8 or MRR below 0.5. Thresholds are configurable CLI options from 0 to 1. JSON reports contain gate status and reasons; failure exits 2. Reviewed source checksum remains mandatory. Provider predictions can be supplied using --predictions; the default is explicitly the offline BM25 baseline. This completes evaluation gate infrastructure, not a live-provider quality benchmark or automatic production certification.

## Completed: provider usage telemetry — 22 October 2026
Embedding and answer success responses emit content-free operation/model/status/provider token counters. Embedding transport failures and HTTP rejections emit status events with unknown token counts. Source text, credentials and user identities are excluded. Counters are provider reported, not billing estimates. Thirteen related tests, Ruff and production-module mypy passed. Persistent per-user metering, dashboards and enforced budgets remain pending; logs are operational telemetry only.
