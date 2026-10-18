# ResearchPilot scope reference

The current master requirements are `LATEST_MASTER_REQUIREMENTS.md`. ResearchPilot is an individual-researcher academic research and writing product, progressing from projects/papers through evidence-supported analysis to manuscript export.

The user accepted the responsive standalone design, then approved replacing the original frontend framework with React/TypeScript/Vite. ADR 0002 records that change. `REFERENCE_IMAGE_REVIEW.md` maps all twelve supplied reference images to future features.

Current working features: identity/profile and owner-scoped research projects with questions, objectives, activity, conflict-safe editing, archive/restore and confirmed soft removal. Dashboard lists actual owned active projects. PDF/RAG, literature analysis, writing, recovery and commercial modules are still incomplete. The user explicitly approved deferring password recovery while proceeding with research features.

No public agent builder, generic workflow canvas, unrelated automation or invented backend activity is in scope. Validate each next vertical feature with user stories, acceptance criteria, contracts and automated checks before adding its UI actions.
