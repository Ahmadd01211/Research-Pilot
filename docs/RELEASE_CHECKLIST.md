# Completion and release gates

Updated 25 October 2026. This is a status checklist, not a claim that the product is ready for public release.

## Implemented in feat/research-completion

- Draft navigation protection, failed-save preservation and explicit conflict review.
- Named blank/article/literature-review starters; selectable outline and live writing counts.
- Immutable matrix CSV/XLSX exports, comparison view and source-provenance sheet.
- Verified volume, issue, pages, article number, publisher and edition metadata; form, formatting preview and raw exports.
- Additive migrations 0016/0017 and readiness derived from the shipped Alembic head.
- Isolated backend tests and frontend component/build checks. No shared runtime changes.

## Remaining product phases

- Reference import: DOI/BibTeX/RIS previews, explicit researcher acceptance and duplicate review.
- Citation completeness: editors/full dates/chapters, disambiguation and formatted manuscript citation output. Current previews remain limited.
- Evidence-linked writing assistance: explicit suggestion acceptance and provider evaluation before enabling generated prose.
- Literature synthesis: source-grounded extraction/suggestions, comparison coverage and researcher approval.
- Document history: explicit source replacement, retained original versions and historical reader navigation.
- Project/matrix/gap conflict review beyond the writing editor.
- Broader representative corpus and real-provider RAG/answer evaluation. Existing seven-case lexical scores are not a universal quality claim.
- Durable provider metering and budget enforcement with a confirmed spending policy.
- Password recovery and real email delivery, production identity policy, trusted proxy/rate controls.
- Retention/Trash/purge/export cleanup after explicit policy approval; no automatic deletion is authorized.
- Coordinated database/original-file backups, a restore drill, dependency/container checks and observability.
- Deployment environment/domain/HTTPS configuration and manual acceptance of the full research workflow.

## Required owner decisions

- Email provider, sender address/domain and privately supplied credentials.
- Per-account AI budget, whether limits block calls, and permission for live-provider tests.
- Retention period or an explicit decision to keep permanent deletion disabled.
- Production host/domain and the access/session policy before public deployment.

Credentials must be configured privately, never committed. Paid calls, live migrations, cleanup and public deployment are not substitutes for these decisions. Synced sources and existing original PDFs remain unchanged.
