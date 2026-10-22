# First real-paper retrieval baseline

The next RAG phase needs a way to distinguish three failures: extraction omitted the answer, chunking split its context, or retrieval ranked a valid answer too low. `backend/scripts/retrieval_eval.py` supplies that measurement before an embedding provider is connected.

The reviewed question set in `backend/tests/mcelheran_retrieval_cases.json` is pinned to the SHA-256 checksum of the supplied 41-page paper. Each case identifies the physical PDF page, evidence type and short phrases that must occur together in one eligible chunk. The script checks that the source bytes match, runs the normal reader and chunker, locates the expected chunks, and ranks all eligible chunks with a small local BM25 baseline. It reports gold coverage, top-five hits and mean reciprocal rank. A later vector retriever can provide ranked chunk IDs with `--predictions`, so the same cases score both approaches. That comparison must use the same source, reader/chunker versions and `--document-id` as the index; otherwise chunk identities differ. Unknown IDs are reported as stale predictions rather than accepted as evidence.

From `backend/`, run:

```powershell
python -m scripts.retrieval_eval --pdf "PATH_TO_SUPPLIED_PDF" --cases tests/mcelheran_retrieval_cases.json
```

No uploaded project data is changed, and this script makes no network or model call. It exits with code 2 if a reviewed answer is absent from all eligible chunks. A low rank is reported, not hidden or automatically rewritten. The JSON report lists chunk IDs and physical page numbers without copying the source text into logs.

The first local baseline had seven of seven answers covered and six of seven in the top five. Reader v20 classifies clearly smaller first-page publication notices as metadata, leaving them readable but outside research evidence. Chunker v11 adds an unambiguous nearby table title to each row's search text, while row and caption source IDs remain separate. Re-running the same local baseline yielded seven of seven top-five hits; six ranked first and one ranked second. This local run used bundled pdfplumber 0.11.9; the backend image pins 0.11.10, so the image must be rerun when Docker is available before treating the score as the production-parser baseline. These seven questions about one article are not an accuracy claim for arbitrary PDFs or the future Google embedding model.

The table-title rule helps users who mention a table number or subject in their question. The tradeoff is a little more repeated text per row and a possible wrong title if page geometry is misleading; the rule refuses multiple plausible captions. The footer rule reduces irrelevant source text but may withhold a small first-page footnote when it resembles publication metadata; the original remains available for review. Both rules are versioned. Existing stored documents must use the reader update action to receive v20 and its v11 chunks; their original PDF and raw text remain unchanged.

Next, add representative papers from other publishers and question types, including missing-answer cases, then run the same benchmark against Google-hosted embeddings, source-scoped retrieval and citation checks. That comparison should drive index and ranking choices. It cannot replace manual review of tables, formulas or figures.
