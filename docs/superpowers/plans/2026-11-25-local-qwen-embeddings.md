# Local Qwen3 embeddings plan (2026-11-25)

Goal: free, private, unmetered semantic search. The user chose Oracle Cloud Always Free
(ARM64) hosting and the open-weights Qwen3-Embedding-0.6B model.

## Design
- New internal `embedder` service (compose profile `local-embeddings`): a tiny FastAPI app
  that loads `Qwen/Qwen3-Embedding-0.6B` at a pinned revision, baked into the image at build
  time (runtime is offline). No published port; reachable only on the compose network.
- Matryoshka truncation to 768 dims then L2 normalisation, so `vector(768)` columns and
  existing SQL stay unchanged (no migration).
- Documents are embedded without an instruction; questions use a research-retrieval
  instruction (Qwen3's asymmetric query format).
- Backend: `RP_EMBEDDING_PROVIDER=google|local`, `RP_EMBEDDING_URL`. An `EmbeddingSpec`
  (provider, model, dimensions, format) drives index identity, so switching providers
  creates new indexes instead of mixing vector spaces. `provider_for(settings)` returns the
  Google or local client with the same `documents()` / `question()` contract.
- Embedder serialises inference (one lock) and bounds input (≤8 texts, ≤8000 chars).
- Image builds on amd64 and arm64 using CPU-only PyTorch wheels.

## Steps (TDD)
1. Tests: settings validation, local client contract (mock transport), embedder server with
   a fake model (truncation, normalisation, query instruction, bounds), index identity per
   provider, capabilities reporting provider.
2. Implement config, embeddings spec/client, indexing/search/router wiring.
3. Embedder server module, Dockerfile, compose profile, .env.example.
4. Frontend: privacy notice depends on provider.
5. Docs: ADR 0010, API, SECURITY, PROJECT_STATUS.
6. Gates + live run: build embedder, index the Transformer paper, hybrid search, timing.
