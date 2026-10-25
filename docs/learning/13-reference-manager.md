# Reference Manager: checked metadata before citation output

This phase stores researcher-verified bibliographic records under a project. `ReferenceRecord` holds title, authors, publication type, year, container, normalized DOI, optional URL and an optional link to an uploaded PDF. The PDF remains the evidence source; the reference record describes its publication. We do not silently turn noisy extracted text into citation metadata.

The FastAPI service checks project ownership before reading or writing. Writes lock the project, reject edits to archived projects, and compare the submitted revision with the current record. That prevents a stale browser tab from overwriting a newer edit. Removal is soft: the reference disappears from the active list while its row remains for future lifecycle work. This is not a retention policy or restore feature.

DOIs are normalized from common URL and `doi:` forms and have a per-project unique index for active records. Exact DOI duplicates are blocked. The UI queries normalized title and year matches and asks the researcher to review them; a title match is only a warning because different works can share similar titles. This approach avoids silently merging distinct publications, at the cost of manual review. The record limit is 500 per project and the active list is bounded to that same size.

Project citation style is stored with its own revision. The choices are APA 7, MLA 9 and Chicago 18. The setting is durable and drives a limited bibliography preview; export does not use it yet. Editions were checked against the [APA Style guidance](https://apastyle.apa.org/style-grammar-guidelines), [MLA handbook](https://style.mla.org/mla-handbook-ninth-edition/) and [Chicago manual](https://www.chicagomanualofstyle.org/cmos18/).

To review: open a project, choose **References**, add a record, link an uploaded PDF if appropriate, then try an exact repeated DOI and a similar title. Change the project style and reload the page. The exact DOI should be rejected, a title match should warn, and the style should persist. Editing and removal require the latest revision. The isolated integration tests exercise those boundaries; actual publisher metadata lookup remains unimplemented.

## Bibliography preview (limited)

`GET .../references/bibliography` formats the active, non-removed records in the saved style. It is read-only: it checks ownership, reads records and the style setting, and makes no writes or external requests. The pure formatter lives in `references/formatting.py`. Each entry returns plain text, text segments with an italic flag, and warnings. The UI renders segments as React text nodes and `<em>`, never as HTML. The response is always marked `preview: true` with a list of limitations, and the page says it must be reviewed. This preview does not claim full style compliance.

**Author convention.** `Family, Given` (exactly one comma) is treated as a person with a known boundary. Anything else (no comma, such as `World Health Organization` or `A. Scholar`, or several commas, such as `Smith, John, Jr.`) is shown exactly as entered and flagged. We never guess where a family name starts, because particles, multi-part surnames and non-Western name orders make guessing unreliable.

**What is supported and tested.** The supported kinds are journal article, book, conference paper (in proceedings), preprint, and a generic layout for "other":
- APA 7 ([reference examples](https://apastyle.apa.org/style-grammar-guidelines/references/examples)): family name plus initials (`J.-P.` for hyphenated given names), comma and `&` before the last author, `(n.d.)` when the year is missing, italic journal, proceedings, book and preprint titles, `[Preprint]`, and the DOI as `https://doi.org/...` (otherwise the URL).
- MLA 9 ([core elements](https://style.mla.org/mla-format/)): the first author inverted and the second in normal order, `et al.` for three or more authors, quoted article titles, italic containers, and the date omitted when missing.
- Chicago 18 notes-bibliography, bibliography entries only ([CMOS 18](https://www.chicagomanualofstyle.org/cmos18/)): the first author inverted, the others in normal order with `and`, up to six authors listed in full, then the first three plus `et al.`, `n.d.` when the year is missing, and `Journal (Year).`

Entries are sorted by author names (diacritics folded, case-insensitive), then year (missing year first), title and record ID. The same order is used for every style.

**Known limitations, shown in the UI.** The stored fields have no volume, issue, pages, publisher, edition, editors, full dates or access dates, so those parts are omitted. Book chapters are not supported, and a book's container field is omitted with a warning. Titles keep the capitalization you entered; no automatic sentence case or title case is applied. APA `2024a`/`2024b` suffixes are not added; colliding entries are flagged instead. Repeated-author dashes, Chicago notes and more than 20 APA authors are not supported. Adding these properly requires new fields, which means a migration, and that is a separate, approved phase.

## Verified publication details - 25 October 2026

Migration 0017 adds bounded volume, issue, pages, article_number, publisher and edition fields. Researchers edit these details explicitly; no metadata is inferred. Older clients that omit the new fields preserve existing values during an update, while an explicit empty value clears a field. CSV/XLSX snapshots include all six fields.

Journal previews now use stored volume/issue/pages or article numbers. Book previews use a stored publisher and edition text. The existing limited-preview labelling remains: editors, full dates, chapters, automatic title capitalization, same-author/year suffixes and notes still need further work. If pages and an article number both exist, the preview uses pages and warns rather than hiding that decision.

Patterns checked against the official [APA journal reference examples](https://apastyle.apa.org/style-grammar-guidelines/references/examples/journal-article-references), [MLA citations by format](https://style.mla.org/works-cited/citations-by-format/) and [Chicago notes/bibliography examples](https://www.chicagomanualofstyle.org/tools_citationguide/citation-guide-1.html). These examples do not establish full manual compliance.

## Offline BibTeX and RIS import preview

The reference page accepts pasted BibTeX or RIS exports up to 100 KB and 50 records. The preview endpoint is owner-scoped and read-only: it does not write records, resolve DOI metadata or contact an outside service. Each candidate is shown before it can be opened in the existing editor. Saving still uses the normal server-side ownership checks, DOI uniqueness, title/year duplicate warning and explicit confirmation. Imported values are not trusted as verified facts, and the researcher can correct them before saving.

The parser maps common title, author, year, journal/proceedings, volume, issue, pages, DOI, URL, publisher and edition fields. It deliberately omits unresolved BibTeX string macros and warns when the title, authors or supported year are missing. It does not execute TeX, fetch metadata, infer author name order, import linked PDFs, or support every RIS/BibTeX extension. Some capitalization and TeX formatting may need review. This is a convenience for common exports, not a lossless citation interchange format.
