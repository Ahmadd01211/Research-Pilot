# Production implementation handoff

## Status and scope

This delivery fulfills the interface-design request through a portable local prototype and documented patterns. It is not a production SaaS application. The earlier identity scaffold was interrupted after files were created; dependencies, migration, runtime, security and builds for that scaffold were not verified in this design task.

The latest master requirements name React + TypeScript + Vite. The earlier approved baseline named Next.js and a thin BFF. Preserve the existing scaffold until the framework/authentication architecture change is explicitly decided; this export does not migrate it or rely on it. The old D: application was not inspected or reused.

## Recommended frontend component boundaries

```text
src/
  app/                  router, shell, providers, error boundary
  components/ui/        button, dialog, drawer, input, table, badge
  components/shared/    page heading, state panel, project selector
  features/
    auth/               auth forms and lifecycle
    projects/           list, cards, details, questions
    library/            upload, documents, filters, preview
    chat/               conversations, scope, typed stream, composer
    literature/         matrix, extraction review, candidate gaps
    writing/            editor, outline, versions, suggestion review
    references/         bibliography, imports, metadata, duplicate review
    exports/            format selection, jobs, history
    settings/           profile, usage and preferences
  lib/api/              generated OpenAPI contracts and transport
  styles/               tokens and global accessibility conventions
```

This structure is a production recommendation, not a claim that these React modules exist. The export intentionally has no framework dependency. The small DOM template functions demonstrate screens; port them into typed components rather than growing a large production `app.js`.

## State and data contracts

Use API data for server-owned resources and a server-state library where it helps. Local UI state owns drawer visibility, selection draft, filters and active tabs. Do not mirror the same project/document data in multiple global stores. Use URL scope for projects, documents, conversations and manuscripts.

Generate TypeScript types from FastAPI's checked OpenAPI. Separate document processing state from reference metadata completeness. A reference without a PDF must not become a retrievable source. A queued export is not completed merely because its POST request succeeded.

Illustrative frontend unions:

```ts
type DocumentState = 'queued' | 'extracting' | 'embedding' | 'ready' | 'failed';
type JobState = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
type ClaimOrigin = 'user' | 'ai_proposal' | 'ai_accepted';
type EvidenceState = 'source_supported' | 'interpretation' | 'insufficient_evidence';
```

Treat these as contract design inputs; exact states must agree with backend transitions. Every evidence link needs stable document/version/chunk identity, source location, supplied excerpt and ownership scope. Table edits need expected revisions and conflict handling.

## Production interaction requirements

| Pattern shown | Required implementation |
|---|---|
| Login/register | Real identity service, secure session/token design, validation, reset, throttling, revocation, generic credential failures |
| Upload | Size/MIME/signature validation, private storage, duplicate policy, durable job, time/resource limits, recovery |
| Document preview | Actual isolated PDF renderer, authorized original/download, reliable page coordinates |
| Research chat | Scope authorization before retrieval, bounded streaming, persisted lifecycle, citation validation, no-evidence result, rate/cost controls |
| Evidence matrix | Validated structured extraction, original and reviewed values, citations, version/conflict history, failure recovery |
| Gap analysis | Explicit corpus boundaries, source-supported limitations, labeled inference, uncertainty, broader-search reminder |
| Writing | Evaluated structured editor, stable citation/claim nodes, sanitized content, autosave concurrency and revision persistence |
| References | Proper BibTeX/RIS parsing, configured DOI provider, normalized metadata, duplicate review, licensed validated citation styles |
| Export | Saved revision snapshot, supported format capability list, robust DOCX/CSV/XLSX renderers, provenance, authorized downloads |
| Usage | Actual measured events, transparent estimates, quotas and failure/unknown states, no invented analytics |

## Security and privacy

Browser-local storage is acceptable for this synthetic prototype, not for production session tokens, passwords or confidential research documents. No auth credentials entered here are persisted. No file bytes are read by the selection interaction. The local server exposes only the design assets, not backend source files or secrets.

On integration, enforce ownership and project scope on every backend operation. Do not trust IDs embedded in editor nodes, citation markers or imported references. Sanitize editor content server-side, validate structured schemas, isolate PDF processing, prevent formula execution in spreadsheet exports, bound AI budgets, and keep source text and credentials out of routine logs.

The prototype's CSV exporter prefixes formula-like cells and quotes fields. The manuscript export strips active HTML and marks the output synthetic. Those protections are narrow prototype checks, not comprehensive security review.

## Tradeoffs explained

- **Portable HTML/CSS:** immediate visual review and easy token reuse without a framework migration. Tradeoff: DOM templates/local state should be replaced with typed feature components for production.
- **Persistent desktop navigation:** stable task orientation for long sessions. Tradeoff: consumes horizontal space; mobile uses a drawer and supporting panels stack.
- **Evidence drawers:** inspect a claim without abandoning the current task. Tradeoff: drawer width limits long reading; provide a full document route.
- **Real matrix tables:** preserve cross-study comparison and screen-reader semantics. Tradeoff: horizontal scrolling on small screens; sticky row headers keep context.
- **Separate AI proposals:** protects authorship and makes acceptance explicit. Tradeoff: one extra review action; it is justified for academic text.
- **No fabricated usage/pricing:** honest review of the product state. Tradeoff: less visually busy dashboards; real metering must supply the eventual data.
- **One sample manuscript:** supports a complete design interaction without simulating a full document database. Tradeoff: other outline sections remain specified rather than falsely populated.

## Verification and next step

JavaScript syntax and DOM interaction tests cover route rendering, state layouts, search/filter, evidence dialogs, local project creation, persistence, suggestion acceptance/versioning, credentials not being stored, editor sanitization, CSV escaping and honest export capabilities. They do not validate rendering, actual browser editor commands, screen-reader behavior, backend authorization, production builds of React code or real academic evidence.

Next: manual design review, then decide Vite versus the existing Next.js scaffold and session versus access/refresh-token architecture before integrating one complete vertical feature. Keep production module implementation incremental; do not implement every screen's backend simultaneously.
