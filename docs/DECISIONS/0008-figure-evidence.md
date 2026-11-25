# ADR 0008: Visual source evidence without vision inference

Accepted, 19 October 2026.

Use original-PDF previews, measured caption/image association with page fallback, and explicit authors' Figure references. Store versioned prose/table-row/figure-caption chunks atomically with extraction. Keep uncertain figure-page prose out of retrieval, while retaining raw text and the original for inspection. Never turn chart labels or bar heights into asserted findings. No vision provider is required.

Amended 24 November 2026: on a page whose figure region is uncertain, withhold passages that are not unmistakable prose (fewer than 25 tokens, under 15% common function words, or letter-spaced) instead of all page prose. Measured on 19 real public papers, whole-page withholding hid 9,553 words of ordinary paragraphs while chart labels arrived as separate short passages. A leak audit of the 93 newly kept chunks found paragraphs, plus one flattened small table beside its caption. Unmatched table captions and fragmented text still withhold all page prose. Legacy unassessed layouts keep the original rule. See learning/17-real-pdf-hardening.md.

Consequences: conservative detection and reduced retrieval recall on uncertain pages; extra PDF transfer for opt-in previews; retained derived records need later lifecycle management. Figure cards are reusable for future chat, but chat integration and embeddings are not implemented here. See learning/05-figure-evidence.md.
