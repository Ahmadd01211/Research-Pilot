# ResearchPilot web

React + TypeScript + Vite. FastAPI owns identity and business logic. No session tokens or passwords are stored in browser localStorage.

Node.js 24 LTS recommended. `npm ci`, then `npm run dev` opens http://localhost:3100. The development proxy targets http://127.0.0.1:8100; set server-only API_PROXY_TARGET if needed. Start the backend through root Compose first.

`npm run lint`, `npm run typecheck`, `npm test`, `npm run build`.

The Docker image serves the compiled static app through an unprivileged Nginx process on 8080, proxies /api/v1 to FastAPI, and falls back to index.html for client routes. `vite preview` is only a local build preview, not a production web server and does not replace this API proxy.

Implemented routes: /, /register, /login, /dashboard, /profile, /projects, /projects/new, /projects/:id and /projects/:id/edit. The standalone design-export remains a separate synthetic-data reference; unimplemented research modules are not represented as functional app pages.

Fonts are self-hosted with license files. See docs/DECISIONS/0002-vite-frontend.md and docs/REFERENCE_IMAGE_REVIEW.md.
