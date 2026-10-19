# Learning 04: readable evidence and the original page

The screen has three distinct representations. Original PDF means PDF.js draws the actual source page, preserving the paper's layout. Raw text means the earlier pypdf extraction for inspection. Readable passages are a separate derivative grouped from measured words. They are not an AI summary and do not replace the original.

## Follow the code

`parse_pdf.py` still extracts raw text with pypdf in its bounded Linux subprocess. It also opens the original with pdfplumber and calls `reader.prepare_layouts`. Both results travel to the parent worker. `extraction.extract_with_layout` validates shape, limits, normalized boxes and word-index references. `processing.finish` stores raw text and layout in the same page-publication transaction. A failed job cannot publish half a reader.

`reader.py` measures x0/top/x1/bottom relative to the rotated CropBox, the visible page PDF.js uses. It converts coordinates to fractions between zero and one. For example, x0=.25 and x1=.40 mean the word begins a quarter of the way across the page and spans 15% of its width. Normalization lets the same box work at different canvas sizes without new extraction. Cropping and rotation need explicit tests; raw PDF coordinates have a different origin from browser canvas coordinates.

Fixed word-spacing tolerances can accidentally merge tightly typeset words. We found this on the supplied paper and used a tolerance relative to font size instead. That uses actual glyph spacing; it does not ask a model to guess what the author wrote. It still cannot guarantee perfect segmentation for every font, language or layout.

The reader normalizes nonbreaking spaces, expands ligatures and removes soft hyphens in its derivative. It never guesses missing letters or silently rewrites citations, numbers and mathematical expressions. Repeated edge text can be excluded from readable passages only after occurring across enough pages; excluded text remains visible in a details section and all raw text remains available. This is a conservative heuristic, with visible limits, not a guarantee of perfect document understanding.

## How highlighting stays tied to evidence

Every readable passage has a deterministic ID and a list of word indices. The ID covers parser/reader identity, physical page number, words and measured boxes. The UI sends no coordinates supplied by another user; it reads the owned server result.

`document-page.tsx` uses URL search parameters for page and passage selection. A passage link also identifies the original checksum and reader version. If these no longer match, highlighting is disabled. If a requested page does not exist, the reader shows an error instead of showing page one under a misleading citation. Later Research Chat can construct the same source links from retrieved passage metadata.

`pdf-canvas.tsx` fetches the original with the user's session, checks its SHA-256 in the browser, then passes a byte array to PDF.js. An unauthorized, missing, changed or unverifiable original is not parsed/displayed. Only after rendering does the canvas draw translucent rectangles over the selected measured word boxes. This is word-level source highlighting, not sentence verification or scientific claim checking.

## Why render a canvas rather than embed the PDF directly?

Canvas gives control over page selection, crop/rotation alignment, highlights, resource limits and error states. It does not execute interactive PDF actions or instantiate a general viewer scripting environment. It needs a separate accessible text alternative, so we keep source text beside it. A complete desktop PDF application has more features; this reader deliberately focuses on evidence reading and verification.

PDF.js loads a self-hosted module worker, fonts and CMaps. The .mjs worker must be served as JavaScript; the live smoke test caught Nginx's generic binary MIME type and we added a targeted mapping. No unsafe-eval, inline-script allowance or third-party CDN was added. The explicit older no-eval flag remains in compatible configuration, but installed version 6 no longer lists it in its types; strict CSP and maintained dependencies are essential.

The viewer fetches a bounded original once and verifies it, which costs up to 20 MiB of initial transfer. Its loading task is destroyed on unmount, pending fetches are aborted, and cancelled page renders do not update the next page. Canvas size and image limits reduce browser memory pressure. These measures do not constitute a complete malicious-file sandbox.

## Older uploads

Migration 0005 adds a nullable layout field without modifying original files or automatically reprocessing existing papers. An older extracted document offers Prepare readable text and highlights. That owned CSRF-protected request queues an upgrade through the existing durable job system. It cannot run again on already prepared or pending work. Archive/removal rules still apply. This operation does not delete originals or introduce a retention policy.

## Where embeddings and chat fit

The user chose Google-hosted embeddings, with a separate configurable answer model. The intended path is: measured source passages → versioned chunks → document embeddings stored in pgvector; question → compatible query embedding → owned selected-source retrieval → stronger chat model → cited answer. Changing the chat model does not require re-embedding source documents. Changing embedding model/dimensions/preprocessing does require a new compatible index. Matching vector dimensions alone does not make different models compatible.

A powerful chat model cannot compensate for wrong/missing retrieved evidence. We will evaluate retrieval, enforce citation/source membership, preserve source links and allow insufficient-evidence responses. Google credentials stay server-side and must never appear in VITE variables or frontend bundles. Free-tier availability/quotas and data-use terms need verification at setup; no live provider calls occur in this reader milestone.

## Try it

Open a paper from its project library. For an older extraction, prepare the reader and wait for processing. Compare PDF and readable text, select Show passage in PDF, switch to Raw, navigate a page and try zoom. Test the Text-only view on a narrow screen. Reload a passage link and confirm the same words highlight. Compare important quotations with the original; readable text does not reconstruct tables or guarantee reading order.

Backend tests cover raw preservation, measured bounds, rotated/cropped pages, reader preparation ownership/CSRF and repeated-margin cleanup. UI tests cover highlighting, version mismatches, unknown/invalid links, raw view, legacy preparation, layout choices, checksum/authorization rejection and loading-task cleanup. A separate PDF.js Node-canvas check rendered the supplied paper with measured overlays; this is static PDF inspection, not browser screenshot automation. The live HTTP smoke also verifies worker/font/decoder assets and unchanged CSP. Visual acceptance of the actual application remains with the user.
