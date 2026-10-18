# ResearchPilot — premium interface design export

18 October 2026 · Scholarly Blue · Local-only design delivery

## Open the design

Open `index.html` in a browser, or run `node serve.cjs` and visit **http://localhost:3200**. The local server binds only to this computer and serves only the public design files and fonts. No installation is needed to view the design. With the server running, use `http://localhost:3200/#/dashboard` to open the workspace directly.

The export contains all 14 requested connected screen families, plus a design-system screen and separate login, registration, and usage views. Use the **State** selector on workspace screens to inspect ready, empty, loading, processing, failure, and success layouts.

## What works

- Screen navigation, responsive sidebar, library table/grid switch, search/filter, ready-source selection, source evidence drawers.
- Local project creation/editing, project research questions, reference metadata edits and manual metadata records.
- Editable literature matrix with source links and browser-local persistence.
- Local manuscript editing, visible autosave, explicit named versions, deliberate restoration, citation marker insertion, and acceptance/dismissal of a prewritten writing suggestion.
- Auth form validation and password visibility as design interactions. No authentication occurs.
- CSV export of the current sample matrix and HTML export of the current manuscript, both explicitly labeled synthetic research.
- Profile editing and actual counts of local preview records. No fabricated AI usage graphs or subscription limits.

## What is not implemented

There is no connected authentication, FastAPI, storage, AI generation, PDF processing, real reference import/DOI resolution, citation-style engine, server export, subscription, or production data service. A PDF selection records filename and size only; file content is not read or uploaded. Processing/failed examples and gap findings are synthetic design states. No claim of production readiness or academic correctness is made by this prototype.

Every paper, author combination, journal title, excerpt, and finding in the sample corpus is fictional. Do not cite these examples in real research. Pricing remains unspecified; there is no checkout or active plan.

Edits use the browser's `localStorage`. Use synthetic data. The security/settings screen can reset this prototype's storage after explicit confirmation. Private browsing, browser storage policies, and opening files under different origins may affect persistence. Files opened directly and pages served at localhost have separate storage.

## Deliverables

| File | Purpose |
|---|---|
| `index.html` | Portable entry point |
| `styles.css` | Semantic CSS tokens, reusable patterns and responsive layouts |
| `app.js` | Connected screens and browser-local design interactions |
| `design-tokens.json` | Framework-independent token handoff |
| `DESIGN.md` | Component, layout, accessibility and interaction specification |
| `SCREEN_FLOWS.md` | Screen-to-screen journeys and state behavior |
| `IMPLEMENTATION_HANDOFF.md` | React/TypeScript integration boundaries and production gaps |
| `assets/` | Self-hosted variable fonts and their SIL Open Font Licenses |
| `tests/` | DOM interaction checks without browser screenshots |
| `serve.cjs` | Optional local preview server |

## Verification

Run `npm ci`, `npm run check`, and `npm test` to reproduce JavaScript syntax and DOM interaction checks. Dependencies are locked in `package-lock.json`. These checks do not establish browser rendering, full accessibility conformance, mobile device behavior, or backend correctness. The user performs manual visual acceptance. No automated browser screenshot testing was performed.

No external runtime network request is needed: fonts and code are local. Fonts are Manrope and DM Sans, bundled from the official Google Fonts repository with their original license text. Inline icons are native SVG paths in `app.js`.

The original application scaffold has been left intact. The newer requirements specify **React + TypeScript + Vite**, while the earlier approved scaffold used **Next.js**. This design is framework-independent; do not silently treat that framework change as resolved or copy the prototype's browser-local data model into a production backend.
