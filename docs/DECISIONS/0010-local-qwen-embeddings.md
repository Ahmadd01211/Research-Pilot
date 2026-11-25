# ADR 0010 — Local Qwen3 embeddings

Accepted 25 November 2026. This extends ADR 0007 and ADR 0009: Google embeddings remain
available, and keyword search remains the default when embeddings are off.

## Context

The user wants semantic search without a paid provider or a shared daily quota. The
free hosted options each carry a cost:
- OpenRouter's free embedding hosts refuse the no-data-collection policy, so they would
  train on paper text.
- The Gemini free tier lets Google use the submitted content.
- Other free tiers expire or are unverified.

The app will be hosted on Oracle Cloud Always Free, which provides up to 4 ARM64 CPUs and
24 GB RAM. That is enough to run a small embedding model on CPU.

## Decision

- **Model:** `Qwen/Qwen3-Embedding-0.6B` (Apache 2.0, multilingual), pinned to a Hugging
  Face revision.
  - The weights live in the `embedder-models` named volume, not in the image. They are
    downloaded on the first start, and later starts load local files only. Rebuilding or
    deleting the image never downloads them again.
  - A `.complete` marker is written only after a full download, so an interrupted download
    resumes on the next start. This was tested by stopping Docker mid-download.
- **Dimensions:** the model was trained with Matryoshka representation learning. We keep
  its first 768 of 1024 dimensions and L2-normalise them. The existing `vector(768)`
  columns, SQL and hybrid RRF search therefore need no migration.
- **Asymmetric inputs:** questions get a research-retrieval instruction prefix, and
  passages are embedded unchanged. This is how Qwen3-Embedding was trained.
- **Separate internal service:** a separate `embedder` container (compose profile
  `local-embeddings`) loads the model once.
  - The API and worker call `POST /v1/embed` over the compose network.
  - The container publishes no port, runs on a read-only root filesystem, and has a
    memory limit.
  - It runs one inference at a time, and batches are bounded to 8 texts of at most 8,000
    characters each.
  - The backend image stays free of PyTorch.
- **Index identity:** each index records its provider, model, dimensions and format
  (`EmbeddingSpec`). `RP_EMBEDDING_PROVIDER=local|google` selects the spec. Switching
  providers creates new indexes instead of mixing vector spaces.
- **Failures:** an unreachable or overloaded embedder is transient, so the durable index
  job retries. Vectors claiming another model or a wrong shape are rejected.

## Consequences

- **Benefits:** it is free with no quota, and paper text never leaves the server. Users can
  re-embed freely, which supports the upcoming indexing and IVF-PQ work.
- **Costs:**
  - The embedder needs about 3 GB of RAM. The image is about 1.9 GB, and the model volume
    is about 1.2 GB.
  - The first start needs internet access to Hugging Face.
  - CPU indexing is slower than a hosted API.
  - The embedder has no authentication of its own; it relies on network isolation.
- **Arm64 support:** the image uses PyTorch CPU wheels, which are published for amd64 and
  arm64.
