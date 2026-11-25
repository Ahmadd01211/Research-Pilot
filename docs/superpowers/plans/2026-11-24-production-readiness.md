# Production readiness plan — 24 November 2026

Branch: `feat/production-readiness`. Order requested by the user: make PDF extraction
reliable first, then production work, then RAG refinement (indexing, IVF-PQ and related).

## Phase 1 — PDF extraction correctness (done)

Method: run the real production path (`extract_with_layout` → `make_chunks`) against
public research PDFs from varied publishers, find failures, fix them test-first, and keep
the corpus as a repeatable probe.

1. **Done — figure findings rejected whole documents.** `quality.py` emitted findings with
   scope `"figure"`, which `QualityFinding` did not allow. Any page with such a finding made
   the whole document fail as `invalid_pdf`, discarding readable text. 4 of 11 real papers
   (GAN, BERT, LoRA, Chain-of-Thought) failed this way. Fixed the schema and added a
   contract test that checks every scope `quality.py` emits.
2. **Done — internal bugs no longer blamed on the user's PDF.** Exceptions in layout
   heuristics and violations of the reader's own output contract now report
   `layout_failure` with a content-free diagnostic in worker logs (exception type and
   file:line only). `invalid_pdf` is reserved for PDFs that pypdf, pdfminer or pdfplumber reject.
3. **Done — silent evidence loss.** Searchable share of readable body text went from 88% to
   about 96% on the real papers. A stray undecodable symbol no longer hides its paragraph,
   and an uncertain figure withholds only chart-like passages (ADR 0008 amended).
4. **Done — time headroom.** Parser CPU limit 90 s and wall 100 s; the extract task has its
   own 160/190 s Celery limits; a test pins the ordering below the 240 s lease.
5. **Done — review fixes.** READER_VERSION bumped with the chunker and quality versions
   (pinned by a test), `layout_failure` is owner-retryable, PDF-library errors stay
   `invalid_pdf`, the rounding bug is fixed and the glyph notice is honest. The
   `backend/scripts/real_pdf_coverage.py` audit is in the repo.

## Phase 2 — AI provider: OpenRouter for answers (implemented, pending real-key check)

- Done: OpenRouter answer adapter (server-only key), shared daily budget enforced by the
  server, keyword (PostgreSQL full-text) retrieval when embeddings are off, and UI showing
  the remaining answers and which provider receives passages. ADR 0009.
- Open: one live check with your real key and chosen free model (answer quality, JSON
  compliance, real quota). Set `RP_ANSWER_DAILY_LIMIT` to your key's actual limit.
- Embeddings stay optional. Semantic retrieval choices move to Phase 4.

## Phase 3 — Production hardening (from SECURITY.md / ROADMAP.md)

Password reset with real email delivery, trusted proxy and abuse limits, backups and a
restore drill, Trash/retention/purge, dependency and image scanning, deployment target.

## Phase 4 — RAG refinement (after the above, with the user)

Indexing strategy, ANN index choice and parameters, retrieval evaluation on real papers.
Note: pgvector offers IVFFlat and HNSW, plus half-precision and binary quantization;
IVF-PQ (product quantization) is not native to pgvector. It would mean FAISS in a service,
or a Postgres extension such as VectorChord. Decide after measuring the corpus size.

## Decisions waiting for the user

1. Who uses production: only you, or other researchers signing up? This changes how much
   of Phase 3 is required, and how the daily AI budget is shared.
2. Hosting target and domain (needed for HTTPS, secure cookies and email).
3. Email provider for password reset.
4. The exact OpenRouter free model and its real daily limit on your account.
