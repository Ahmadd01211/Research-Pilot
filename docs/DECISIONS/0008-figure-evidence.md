# ADR 0008: Visual source evidence without vision inference

Accepted, 19 October 2026.

Use original-PDF previews, measured caption/image association with page fallback, and explicit authors' Figure references. Store versioned prose/table-row/figure-caption chunks atomically with extraction. Keep uncertain figure-page prose out of retrieval, while retaining raw text and the original for inspection. Never turn chart labels or bar heights into asserted findings. No vision provider is required.

Consequences: conservative detection and reduced retrieval recall on uncertain pages; extra PDF transfer for opt-in previews; retained derived records need later lifecycle management. Figure cards are reusable for future chat, but chat integration and embeddings are not implemented here. See learning/05-figure-evidence.md.
