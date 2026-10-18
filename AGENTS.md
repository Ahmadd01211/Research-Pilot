# ResearchPilot greenfield
This is the new application. Do not inspect or reuse D:\ResearchPilot.
Read PROJECT_STATUS.md and the relevant feature docs before changing code.
Keep FastAPI authoritative for business logic and authorization; React/TypeScript/Vite handles presentation; Vite (development) or Nginx (built app) proxies same-origin /api/v1 requests. The Vite migration was explicitly approved by the user.
Use focused vertical slices. Never add fake integrations, counts or successful jobs.
Run backend lint, typecheck, tests and frontend lint, typecheck, tests, build for affected changes.
Use only disposable rp_greenfield_test databases for destructive test setup.
Never remove application Docker volumes or reset application data.
The user manually tests visual UI. No browser screenshot automation.
Explain important decisions, benefits and tradeoffs as work progresses.
