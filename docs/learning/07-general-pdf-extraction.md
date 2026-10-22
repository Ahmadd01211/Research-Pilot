# Building a safer, general PDF-to-evidence pipeline

## Back-matter section boundaries (reader v22, chunker v12)

The supplied paper's physical page 26 (printed page 400) previously placed acknowledgments, data availability, ORCID and the start of endnotes in one body passage. That was poor retrieval input: it mixed administrative metadata with substantive notes and highlighted all those sections together. The shared reader now recognizes standalone scholarly back-matter headings from measured text lines, carries the current section across page breaks, starts a new passage at each numbered endnote, and resets to body text at appendices. This is a general heading/geometry rule, not a page-number or paper-specific patch.

Funding, acknowledgments, ORCID, conflict statements and bibliography entries remain readable but are withheld from research-evidence chunks. Data availability and individual endnotes stay eligible, labelled with their source role. An endnote that continues onto the next page receives an explicit number in its search text, while its original passage and PDF coordinates remain unchanged. The real 41-page sample now yields 378 eligible chunks; all seven reviewed answer locations remain covered and all seven reach the top five in the offline lexical baseline. This is not a live hosted-embedding or answer-accuracy result.

The reader and chunker versions changed, so existing uploads show **Update readable text and highlights** before using this extraction for new indexing. Any previous embedding index has an old version identity and will not be treated as current. Researchers must verify unusual publisher headings; the recognized heading list is deliberately conservative, so it cannot guarantee every possible PDF back matter is separated.

Reader v21 extends continued-table parsing from at most six numeric columns to up to eight measured columns with strict Yes/No or numeric leaf values. This covers compact end-of-table rows such as controls and observations. The rule still requires a printed continued caption, sequential numbered headers, stable measured gutters, one value per data column, and a row label. It leaves Notes and following prose outside the table. If those conditions fail, the page remains visibly readable but withheld from retrieval rather than being embedded as a flattened table paragraph.

The goal is not to turn every PDF into perfect text. PDFs are page-layout files: a text extractor may return words in the wrong order, merge table columns, omit scanned text or expose unusable equation glyphs. The pipeline should preserve the source, make measured interpretations, test their boundaries and tell retrieval when not to trust them.

## Processing stages

1. Keep the original PDF immutable and checksum it. This makes every later source link verifiable and lets a reader compare derived text to the exact uploaded bytes.
2. Extract raw page text and measured words separately. Raw text is a preservation/debugging path; word boxes support visible passages and structured layout parsing. Neither representation replaces the original.
3. Run conservative structural adapters. Prose passages, table rows, figure captions and equations have different extraction and retrieval needs. For example, the continued-table adapter in `backend/app/modules/documents/continued_tables.py` needs a continuation caption, repeated numbered headers and measured alignment before creating cells. It does not assume that a sequence of numbers means a table.
4. Validate structure and source anchors. `quality.py` checks that cells/passages point to the measured words, table rows have consistent shape, and captions have a nearby validated table. Quality version v2 recognizes when table bounds include the caption line as well as when a table begins just below it.
5. Create small, labelled, source-anchored chunks. A table row chunk includes its row label and the relevant column headings with each value, so retrieval can distinguish (for example) “Use AI” from “Do not use AI.” Section labels are inherited where detected; notes stay separate. Chunker version v9 makes the changed policy explicit in identities.
6. Gate retrieval, not reading. Ambiguous table rows or damaged passages can be withheld from retrieval while the PDF, raw text and readable view remain available for inspection. A warning is a useful outcome: it avoids presenting an uncertain extraction as strong evidence.

## Why conservative parsing is a good tradeoff

It reduces silent column/value mixups and creates regression-testable contracts. A false positive can still be caught with bounds, row-shape and anchor checks; a false negative loses retrieval coverage but leaves source material intact and reviewable. We prefer a visible “needs review” over fabricated certainty. The cost is that some usable evidence may not be searchable until a later detector or OCR path supports it.

No heuristic proves semantic correctness. A regular, aligned table may still have a wrong cell association; an unusual table may look like prose; publisher sidebars and multi-column articles may confuse reading order. Automatic assessment is a safety net, not a human review or scientific validation.

## Versions and reprocessing

Reader, quality and chunker versions belong to derived evidence identities. When extraction behavior changes, old derived layouts must not masquerade as current. New uploads use current rules; existing documents need the explicit Update readable text and highlights operation. This costs a bounded reprocessing job but avoids silently rewriting a user's saved evidence. Prior derived versions and source originals remain available under existing retention behavior.

## Regression testing strategy

The synthetic PDF corpus builds actual PDFs and runs the real geometry/parser stack. It covers multiple table detectors, continued headers, ambiguous rows, notes, rotations/crops, figures, equations, links, fragmented text and front matter. The shared chunk contract ensures table values remain paired with labels. A supplied real paper is also checked for expected page/column/row values; this catches interactions synthetic fixtures cannot model.

Tests can prove these cases work and that uncertain cases are gated. They cannot prove correctness for an unlimited set of third-party PDFs. Scanned pages still need OCR, and handwriting, inaccessible fonts, complex math and novel publisher layouts remain explicit limitations. Embeddings and chat have not been called by this extraction phase.

## Page navigation

The reader's “Go to page” field validates an integer against the physical PDF page count, then uses the same page-selection path as next/previous navigation. Physical PDF pages are deliberate because printed labels can restart, be Roman numerals or differ from the PDF's actual page index. The tradeoff is that a reader searching for a printed page number must map it to the physical page shown by the PDF viewer.

## Regression tables with grouped model columns

Reader v19 adds a geometry-based adapter for tables with sequential numbered model headings. It collects multi-line/grouped headings up to the first aligned data row, maps coefficient cells using the measured model starts, preserves genuine blank cells, and joins the following parenthesized standard-error line to its coefficient. Edge-running publisher text is excluded before row construction so vertical journal furniture cannot become a row label. Text inside a numeric model column that is not a coefficient or standard error makes the candidate table uncertain instead of silently becoming data. Chunker source-types-v10 uses the same labelled-row contract as the other table adapters.

This design improves retrieval because each row chunk carries its row label, all model headings, and the coefficient with its standard error. It also supports incomplete model rows without shifting later values left. The tradeoff is deliberate conservatism: only aligned, numbered-model layouts with enough valid rows are reconstructed. A different kind of regression table may stay under review until another reusable detector is supported; no table heuristic can prove the paper's statistical meaning.

On the supplied paper's physical page 21 (printed page 395), the detector produced 18 data rows and seven model columns. It retained “Full owner and revenue sample,” paired the estimates with their parenthesized errors, left absent estimates blank, and created 18 labelled table-row chunks. The page passed its structural quality check. A generated PDF fixture also tests offset grouped headings, blanks, separate errors, and publisher text aligned with a data row.

The updated synthetic report covers 25 generated layouts; this is repeatable coverage for known structures, not proof that arbitrary PDFs extract without error. Existing documents must be explicitly reprocessed after a reader-version change. Originals and raw extracted text remain the comparison source.
