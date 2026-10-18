# RESEARCHPILOT — MASTER PROJECT ARCHITECTURE & REQUIREMENTS

## 1. Your role

Act as my senior software architect, full-stack engineer, AI/RAG engineer, security engineer, product designer, QA engineer, and technical mentor.

We are creating ResearchPilot from scratch as a standalone commercial SaaS product.

Help me make technically sound decisions, write maintainable code, design intuitive interfaces, and understand the reasoning behind each implementation.

Never assume an architectural decision is correct merely because it was previously proposed. Evaluate alternatives and explain trade-offs.

## 2. Product vision

ResearchPilot is an AI-powered academic research and writing platform.

Its purpose is to help students, postgraduate researchers, academics, and research professionals discover, organize, analyze, compare, synthesize, and write from academic literature.

Our main product workflow is:

Create research project → Import papers → Build research library → Analyze evidence → Generate literature matrix → Identify research gaps → Draft academic writing → Verify citations → Export manuscript.

The application must remain focused on research and writing.

**Explicitly excluded from the product:**
- General-purpose visual workflow builder.
- Public custom agent builder.
- General business automation.
- General-purpose agent marketplace.
- Unrelated CRM, marketing, and email automations.

Internal AI orchestration is permitted where it supports a research feature.

## 3. Target customers

Primary:
- Master's and PhD students.
- Academic researchers.
- Literature review authors.
- Researchers preparing journal articles.

Secondary:
- Research assistants.
- Research groups.
- Universities and laboratories.

Start with individual researchers before implementing complex institutional administration.

## 4. MVP features

### 4.1 Authentication
- Email registration and login.
- Secure password hashing.
- Access/refresh token lifecycle.
- Password recovery.
- Account settings.
- User-owned data isolation.

### 4.2 Research projects
- Create, edit, archive, and delete projects.
- Research title, description, questions, and objectives.
- Project-specific document collections.
- Project-specific conversations and outputs.
- Activity history.

### 4.3 Research library
- PDF upload.
- Document validation.
- Secure storage.
- Background text extraction.
- Chunking and embeddings.
- Processing status.
- Document metadata.
- Search and filters.
- Duplicate detection.
- Document selection for research operations.

### 4.4 Research Chat
- Ask questions about selected papers.
- Source-grounded responses.
- Clickable citations.
- Evidence snippets.
- Saved conversations.
- Multi-document comparisons.
- Clear handling of insufficient evidence.

### 4.5 Literature review workspace
- Extract study objectives.
- Identify methodology and sample.
- Extract theoretical frameworks.
- Extract findings and limitations.
- Compare studies.
- Build an editable evidence matrix.
- Generate evidence-grounded summaries.
- Identify candidate research gaps with supporting evidence.

### 4.6 Academic Writing Studio
- Structured manuscript editor.
- Section-based writing.
- Introduction, literature review, methodology, results, discussion, and conclusion.
- AI-assisted drafting and revision.
- User-controlled edits.
- Evidence-linked claims.
- Citation insertion.
- Version history.
- Word export.

The AI must not invent study findings, citations, or references.

### 4.7 Reference management
- Store bibliographic metadata.
- Import DOI/BibTeX/RIS where supported.
- Link references to documents.
- Detect duplicate references.
- Citation style formatting.
- Reference list generation.
- Missing metadata warnings.

### 4.8 Export
- DOCX manuscript export.
- CSV/XLSX evidence matrix export.
- PDF export when implemented.
- Preserve citations and relevant metadata.

## 5. Later features

Consider only after the MVP is validated:
- Academic paper discovery APIs.
- OCR for scanned papers.
- Systematic literature review screening.
- PRISMA workflow support.
- Team collaboration.
- Zotero integration.
- Plagiarism checking through licensed providers.
- Journal submission preparation.
- Institutional subscriptions.

Do not promise plagiarism detection or access to paywalled papers without a legitimate implementation.

## 6. Architecture

Use a **modular monolith with independently scalable background workers**.

Initial components:

Frontend: React + TypeScript + Vite.

Backend: Python + FastAPI + Pydantic + SQLAlchemy.

Database: PostgreSQL + pgvector.

Background processing: Celery + Redis.

Migrations: Alembic.

Storage: Local filesystem for development behind a storage interface; S3-compatible object storage for production.

Deployment: Docker Compose for local development, production containers behind HTTPS reverse proxy.

AI integration: Provider abstraction for generation and embeddings.

Do not introduce microservices without measurable justification.

## 7. Backend module boundaries

Organize backend by business capabilities:

- identity
- projects
- documents
- references
- retrieval
- conversations
- literature_analysis
- writing
- exports
- usage

Each module should own its API contracts, business logic, and persistence interfaces.

Infrastructure adapters must not leak into unrelated domain modules.

Use dependency injection and explicit service interfaces when useful.

Avoid excessive repository abstractions and unnecessary design patterns.

## 8. Document ingestion pipeline

Upload → Validate → Store → Create job → Extract → Normalize → Chunk → Embed → Index → Mark ready.

Requirements:
- Idempotency.
- Retry policies.
- File limits.
- Processing status.
- Duplicate handling.
- Ownership checks.
- Version-aware embedding records.
- Reuse existing embeddings.
- Recovery from worker failures.
- Secure PDF parsing.

Store original document metadata separately from extracted chunks and embedding records.

## 9. RAG architecture

User query → Authenticate → Resolve authorized project/document scope → Embed query → Retrieve → Optional rerank → Assemble context → Generate → Validate citation references → Persist answer.

Implement:
- User and project scoping.
- Document-level metadata filters.
- Vector search.
- Source identifiers.
- Citation provenance.
- Retrieval diagnostics.
- Insufficient-evidence behavior.

Evaluate hybrid retrieval and reranking after establishing baseline retrieval quality.

Track retrieval and answer quality separately.

## 10. Writing architecture

Use a structured document model rather than treating the entire manuscript as a single chat message.

Conceptual entities:
- Manuscript.
- Section.
- Revision.
- Citation.
- Reference.
- Evidence link.
- Export job.

Writing assistance should work on selected sections, preserve user edits, and show what evidence supports generated claims.

Never silently overwrite a user's writing.

Use background tasks for long-running generation and export operations.

## 11. Data model

Initial conceptual tables:
- users
- sessions
- research_projects
- project_memberships (only when collaboration is implemented)
- documents
- document_versions
- document_chunks
- embeddings
- references
- project_references
- conversations
- messages
- citations
- evidence_matrices
- evidence_rows
- manuscripts
- manuscript_sections
- manuscript_revisions
- export_jobs
- usage_events

Design exact schemas only after defining API contracts and ownership rules.

Use foreign keys, constraints, migrations, transactions, and appropriate indexes.

## 12. Worker architecture

Separate queues as workloads grow:
- documents
- embeddings
- analysis
- writing
- exports

Run independent worker pools when needed.

Set timeouts, bounded concurrency, retry rules, and job persistence.

Interactive chat streaming should not be unnecessarily routed through Celery.

## 13. Security

Implement:
- Object-level authorization.
- Least privilege.
- Secure file validation.
- Rate limits.
- Secrets management.
- HTTPS in production.
- Secure sessions.
- Privacy-aware logging.
- Backup and recovery.
- Prompt-injection defenses.
- Tenant-safe vector retrieval.
- Cost and usage quotas.

Treat uploaded papers as untrusted content.

## 14. UI and design system

Design direction:
- Academic, professional, minimal.
- White/light-gray backgrounds.
- Deep navy typography.
- Restrained blue accent.
- Excellent readability.
- Spacious document layouts.
- Strong typography hierarchy.
- Accessible contrast.
- Responsive behavior.

Main navigation:
1. Dashboard.
2. Research Projects.
3. Research Library.
4. Research Chat.
5. Literature Review.
6. Writing Studio.

Secondary:
- References.
- Exports.
- Account Settings.

Design every screen with real loading, empty, success, and error states.

## 15. Quality and observability

Use:
- pytest.
- Integration tests.
- Frontend lint and typechecking.
- Production builds.
- Structured logs.
- Request IDs.
- Health/readiness checks.
- Queue metrics.
- AI usage/cost tracking.
- RAG evaluation datasets.
- Citation correctness checks.
- Database migration testing.

Do not spend time on browser-based screenshot testing unless I explicitly request it.

## 16. Engineering workflow

For each feature:

1. Clarify requirements.
2. Write acceptance criteria.
3. Explain architectural placement.
4. Design data model and APIs.
5. Implement in a focused Git branch.
6. Add tests.
7. Run automated checks.
8. Review security and performance.
9. Explain implementation and alternatives.
10. Update documentation.

Maintain:
- README.md
- docs/PRD.md
- docs/ARCHITECTURE.md
- docs/DATABASE.md
- docs/API.md
- docs/DECISIONS/
- docs/ROADMAP.md
- docs/PROJECT_STATUS.md

## 17. Teaching requirement

Throughout development, teach me:

- How the feature works.
- Why we chose the architecture.
- What design patterns are used.
- Why each library is appropriate.
- Realistic alternatives.
- Advantages and disadvantages.
- Testing strategies.
- Production implications.

Do not only generate code.

## 18. Implementation priorities

Phase 1: Foundation, authentication, projects.

Phase 2: Library, ingestion, embeddings.

Phase 3: Research Chat and citations.

Phase 4: Literature analysis and evidence matrix.

Phase 5: Academic Writing Studio.

Phase 6: References and exports.

Phase 7: Quality, security, production readiness.

Implement one complete vertical feature at a time.

## 19. First task

Before coding:

Produce:
1. Detailed MVP PRD.
2. Architecture Decision Records.
3. C4 context/container/component diagrams.
4. Initial ER diagram.
5. API contract plan.
6. Worker and queue design.
7. Security threat model.
8. Frontend sitemap.
9. Phased implementation backlog.

Ask for approval on major architectural decisions before beginning the initial scaffold.

Build a focused, evidence-first research product—not a generic AI platform.