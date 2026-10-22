# Docling PDF parser pilot — 22 October 2026

## Scope and reproducibility

This is a read-only, offline comparison, not a change to production ingestion. The test source is the supplied 41-page McElheran et al. PDF, SHA-256 `d2a5a863b3862fd8f941de89d87eba0a43857adc29b476bd03ddcc7a408c0227`. Docling 2.141.0 ran on Windows/Python 3.12 in an isolated temporary virtual environment. Its standard PDF pipeline had table structure enabled and OCR, picture descriptions, and chart extraction disabled. `backend/scripts/docling_pilot.py` records labels, table cells, hyperlinks, and page bounding boxes. The full conversion succeeded. The first run, including model downloads/initialization, took 475.58 seconds; a cached run on pages 8–22 took 65.14 seconds, and cached page 34 took 14.83 seconds. The isolated environment occupied about 1.3 GB and the two downloaded model caches about 0.49 GB on this machine. These times and sizes are environment-specific, not a benchmark for other hardware.

The current pdfplumber reader plus chunker and seven-question local lexical evaluation took 5.33 seconds in its running Linux container. It produced 378 eligible chunks, covered all seven reviewed answer locations, and ranked all seven in the top five. Docling output was *not* fed through this chunker or retrieval test, so these figures are not an apples-to-apples answer-quality score.

## Observed results

| Source case | Docling output | Retrieval implication |
| --- | --- | --- |
| Page 8, Table 2 | Ten rows, two columns; definitions including machine learning paired with their labels. | Strong candidate for table-row evidence. |
| Page 9, Figure 1 | Chart region and caption are distinct from ordinary text; a separate logo region is also labelled `picture`. | Figure evidence is usable after filtering decorative regions. |
| Page 18, Table 6a | 22 rows and seven columns, but `Prior business` and `Owner age (35–54)` merge in one label cell; some coefficients and standard errors merge or shift. | Must fail row-association quality checks; do not index as a trusted table. |
| Page 21, Table 7 | 24 rows and eight columns, but the venture-capital coefficient `0.1071***` is assigned to the following `Startup capitalization` row. Caption text also appears in table header cells. | A direct switch would create a wrong answer to one reviewed question. |
| Page 22, Table 7 continued | Six rows and eight columns; controls and Yes values are aligned. | Promising for continued-table support. |
| Page 26–27, back matter | Data availability, ORCID, ENDNOTES, and numbered notes are separate elements. The continuation of note 16 on page 27 is an unnumbered list item. | Better section boundaries, but cross-page note identity still needs our rule. |
| Page 34, Table A3 | 39 rows and four columns; `Funded by VC` pairs with 18.8/5.9 and `Hold advanced degree` with 8.4/5.3. | Strong candidate for appendix table evidence. |
| Hyperlinks | Docling exposes one hyperlink in its structured items (the page 26 ORCID link). The original PDF has 17 link annotations counted by pdfplumber. | Keep a separate PDF-annotation pass and compare link coverage before replacing the current link extraction. |
| Decoration | Docling reports 51 `picture` items over 41 pages, including repeated journal logos, and classifies page 18 Wiley download text as ordinary text. | Source-furniture filtering remains necessary. |

Docling supplied page provenance for every reported item in this run. Its boxes are element-level and use bottom-left PDF coordinates. ResearchPilot's word-level highlighting would still need a measured word alignment step or a coarser, honestly labelled element highlight.

## Decision

Do not replace the current parser wholesale. The pilot demonstrates that Docling is useful for common tables and document structure, but its dense regression-table row errors could contaminate embeddings. The next safe architecture is an **optional, versioned Docling candidate parser** behind the existing source-quality gate. Normalize Docling elements into ResearchPilot's page/role/table contract, reject rows whose measured source alignment is uncertain, retain the original PDF and separate link annotations, and evaluate both parsers on more publisher styles before choosing a default. Running Docling only on pages the current parser marks uncertain may control cost, but should be tested rather than assumed to improve quality. No application data or deployed ingestion path changed during this pilot.
