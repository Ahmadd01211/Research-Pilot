# Decision — Google-hosted embeddings with independent chat model

19 October 2026. The user explicitly selected hosted embeddings and asked to use a Google free-tier API key. They also requested a more capable chat model to synthesize retrieved evidence. This records direction; the provider integration is not implemented in the source-reader milestone and no research content has been sent to Google.

Use separate server-only embedding and generation configuration. Persist provider, exact embedding model, output dimensions, document/query task or prompt strategy, normalization and chunker/reader identity with the index. Index and query embeddings must remain compatible. Reject mismatched configuration; do not silently mix vectors. A chat-model change is independent of the index, while embedding changes require versioned reindexing.

Official docs checked on this date list gemini-embedding-2 with a free tier for text and independently priced generation models. Availability, quotas and account access must be rechecked at setup. Do not assume every flagship model is free or automatically fall back to a paid model. Free-tier content may be used to improve Google products subject to its applicable terms; choose non-sensitive test material and review data-handling terms for production/unpublished research. API keys must live in ignored server environment/secret storage, never in chat, version control, VITE variables, browser requests or logs.

Next implementation: configured embedding adapter and durable indexing, pgvector identity/migrations, owned selected-source retrieval, then independent chat generation with citations, explicit uncertainty, evidence membership checks, budgets/rate-limit handling and evaluation. A stronger answer model improves synthesis but does not guarantee accurate retrieval or supported claims. No model/key is yet configured, and no provider-backed result should be advertised until real integration checks pass.

Sources: https://ai.google.dev/gemini-api/docs/embeddings and https://ai.google.dev/gemini-api/docs/pricing .
