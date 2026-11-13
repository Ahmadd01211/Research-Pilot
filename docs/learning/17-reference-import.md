# BibTeX and RIS reference import

Researchers usually already keep a library in Zotero, Mendeley or EndNote. Import lets them bring those records into a project without retyping them, but it keeps the Reference Manager's rule: a record is saved only after the researcher has reviewed it.

## Flow

1. **Choose a file** on the References page (Import file). The format is preselected from the extension (`.ris` → RIS, otherwise BibTeX) and can be changed.
2. **Preview**: `POST /references/import/preview` with `{format, text}`. The server parses the text and returns one candidate per entry with `errors`, `warnings`, `importable` and `duplicate_of`. Nothing is written.
3. **Review**: clean entries are preselected. Entries with errors cannot be selected. Probable duplicates are shown but left unselected.
4. **Import**: `POST /references/import` with `{request_id, items}`. Each item is a normal reference payload, validated by exactly the same `_validate` used for manual entry (title, http(s) URL, DOI format, same-project PDF, DOI uniqueness). The batch is atomic: any invalid item rejects the whole request, and its message names the item number.

## Why the server validates the submitted items again

The preview response is convenience data held by the browser. The import request could have been edited or replayed, so FastAPI treats it like any other user input. This keeps business rules in one place: a record created by import is indistinguishable from one typed by hand.

## Idempotency

A batch import is the operation most likely to be retried after a timeout, and records without a DOI have no natural key to prevent duplicates. Migration 0017 adds `reference_imports(project_id, request_id, request_hash, reference_ids)`, unique per project and request. A retry with the same ID and payload returns the original records; the same ID with different content is rejected with 409. The project row is locked during import, so the check and the insert cannot race. The browser keeps the request ID until the selection changes, so pressing Import again after a failure is safe.

## Parser design and tradeoffs

The parsers in `app/modules/references/importing.py` are small, in-house and linear. A library (bibtexparser, rispy) would cover more edge cases but would add a dependency for eight fields, and some of them parse with grammar engines whose cost on hostile input is harder to bound. Ours scan the text once, track brace depth with a counter (no recursion), and stop at 500 entries. The server limits text to 1,000,000 characters. Nginx allows a 4 MB body only on the two import routes, since JSON escaping can double BibTeX's size; every other API route keeps the 256 KB cap.

**BibTeX** supports `{…}` and `"…"` values, `#` concatenation, `@string` macros with standard month names, `@comment`/`@preamble`, and both `{}` and `()` entry delimiters. Text outside entries is ignored, as BibTeX itself does. Common LaTeX is converted to Unicode: accents (`{\"u}` → ü, `\c{c}` → ç), special letters (`\ss`, `\o`), escapes (`\&`, `\%`), style commands (`\emph{…}`) and dashes. Unknown commands are **kept as visible text with a warning**, never removed silently. DOIs and URLs lose only escapes and braces, so `--` in an identifier is not turned into a dash.

Authors follow BibTeX's own name rules rather than a guess. `Last, First` is kept; `First von Last` becomes `von Last, First` (`Ludwig van Beethoven` → `van Beethoven, Ludwig`), and a fully braced name such as `{World Health Organization}` is kept as an organisation. `and others` is dropped with a warning.

**RIS** reads `TAG  - value` lines, joins continuation lines, and requires each `TY` record to end with `ER`. Authors come from `AU`/`A1` (conventionally already `Last, First`). The container is taken from `T2`, `JF`, `JO`, `BT`, `J2` or `JA`; the year from `PY`, `Y1` or `DA`. Only the first of several URLs is kept, with a warning.

Type mapping: article/JOUR → journal; book/BOOK → book (container cleared, since the formatter does not use it for books); inproceedings/CONF → conference; `@unpublished`, arXiv `@misc` and UNPB → preprint; chapters → other, with the book as container and a warning, because chapter formatting is not supported.

## What is reported, and how

- **Errors (cannot import):** missing title, no authors (including editor-only entries), over-long fields, a DOI already in the project, or the same DOI earlier in the file.
- **Warnings (can import):** an unrecognised DOI or non-http URL (left empty), a year outside 1500–2100, more than 20 authors (first 20 kept), unknown LaTeX, multiple URLs, chapters, and probable duplicates matching the normalised title and year, either in the project or earlier in the file.

Malformed files fail as a whole with a line number (BibTeX) or record position (RIS), because the rest of a file with unbalanced braces cannot be trusted.

## Not covered

DOI lookup (fetching metadata from Crossref), abstracts, pages/volume/issue, editors as a separate role, and linking an imported record to a PDF automatically. Imported metadata is only as good as the exporting tool's; researchers should still check records against the publisher.

## Testing

`tests/test_reference_import.py` covers the parsers directly (LaTeX, names, macros, kinds, RIS continuation, malformed input, limits) and the API (preview never saves, duplicate detection, idempotent replay, conflicting replay, atomic failure, archived projects, other users). `frontend/tests/reference-import.test.tsx` covers preselection, disabled error rows, literal rendering of markup-like titles, and that a retried import reuses the same request ID.
