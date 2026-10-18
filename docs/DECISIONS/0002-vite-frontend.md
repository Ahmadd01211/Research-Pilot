# ADR 0002 — React, TypeScript and Vite frontend

Status: accepted. The user explicitly approved switching the frontend from Next.js to Vite on 18 October 2026.

## Context

The first scaffold used Next.js. The latest master requirements specify React + TypeScript + Vite, with FastAPI authoritative for business logic. The user has visually accepted the standalone responsive design and supplied twelve reference screenshots.

## Decision

Use React/strict TypeScript, Vite, React Router declarative routes, React Hook Form/Zod, and TanStack Query for account server state. Preserve the Next.js source in `docs/archives/frontend-nextjs-before-vite.zip`; it is not part of the active build. Keep the standalone design export and user reference images unchanged.

Browser code calls relative `/api/v1` URLs. Vite proxies during development; an unprivileged Nginx container serves the compiled static assets and proxies the API for the built app. The FastAPI origin and CSRF checks remain authoritative. A browser-side router guard improves navigation but does not provide backend authorization.

Public `VITE_` configuration must never contain secrets. No Node BFF or Next-specific server components remain. Production does not use the Vite development server. Nginx supports client-route fallback, request size limits, no-store API responses and streaming-compatible proxy buffering settings.

## Tradeoffs

Benefits: frontend and backend responsibilities are explicit; local frontend iteration is straightforward; the app compiles into portable static assets. Costs: client-side rendering needs deliberate marketing SEO/prerendering later, and hosting must support route fallback and a secure API proxy. Reconsider server rendering if measured public-page needs justify it; do not reintroduce a second business-logic backend.

## Authentication boundary

This framework migration retains the previously approved opaque database-backed sessions in HttpOnly cookies. It does not silently redesign authentication into access/refresh tokens. Latest requirements mention that token lifecycle; record a separate ADR before changing it. Both patterns can support secure browser authentication, but mixing them without a defined revocation/CSRF/storage model would increase complexity. The current identity slice is not full MVP authentication: recovery, account verification, administrative session management and production abuse policy remain subsequent work.

## Validation

Run frontend lint, strict types, component/client tests and a production build. Verify API contracts are generated from FastAPI. Use disposable PostgreSQL/Redis tests for real identity persistence, ownership, session rotation/revocation, CSRF and rate limits. Test the built app's same-origin proxy and reload paths over HTTP. Visual browser tests are performed by the user; no automated screenshots.
