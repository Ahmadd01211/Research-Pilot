"""Conservative, offline parsers for common BibTeX and RIS reference exports."""

import re
from collections.abc import Iterator

from fastapi import HTTPException

from app.modules.references.schemas import ReferenceImportItem

MAX_IMPORT_BYTES = 100_000
MAX_IMPORT_RECORDS = 50


def parse_import(format: str, content: str) -> list[ReferenceImportItem]:
    if len(content.encode("utf-8")) > MAX_IMPORT_BYTES:
        raise HTTPException(413, "Import text is too large (maximum 100 KB)")
    if format == "ris":
        records = _parse_ris(content)
    elif format == "bibtex":
        records = _parse_bibtex(content)
    else:
        raise HTTPException(422, "Choose BibTeX or RIS")
    if len(records) > MAX_IMPORT_RECORDS:
        raise HTTPException(413, "Import contains too many records (maximum 50)")
    return [_to_item(kind, fields) for kind, fields in records]


def _parse_ris(content: str) -> list[tuple[str, dict[str, list[str]]]]:
    entries: list[tuple[str, dict[str, list[str]]]] = []
    kind = ""
    fields: dict[str, list[str]] = {}
    for raw in content.splitlines():
        line = raw.strip()
        match = re.match(r"^([A-Z0-9]{2})\s{0,2}-\s?(.*)$", line)
        if not match:
            continue
        tag, value = match.groups()
        if tag == "TY":
            if kind and fields:
                entries.append((kind, fields))
            kind, fields = value.upper(), {}
        elif tag == "ER":
            if kind and fields:
                entries.append((kind, fields))
            kind, fields = "", {}
        elif kind:
            fields.setdefault(tag.casefold(), []).append(value.strip())
    if kind and fields:
        entries.append((kind, fields))
    return entries


def _bib_entries(content: str) -> Iterator[tuple[str, str]]:
    position = 0
    while match := re.search(r"@([A-Za-z]+)\s*([({])", content[position:]):
        start = position + match.end()
        opener = match.group(2)
        closer = "}" if opener == "{" else ")"
        depth, quoted, escaped = 1, False, False
        end = start
        while end < len(content) and depth:
            char = content[end]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = not quoted
            elif not quoted and char == opener:
                depth += 1
            elif not quoted and char == closer:
                depth -= 1
            end += 1
        if depth:
            raise HTTPException(422, "BibTeX entry has unmatched braces or parentheses")
        body = content[start:end - 1]
        # @string, @comment and @preamble do not represent references.
        entry_type = match.group(1).casefold()
        if entry_type not in {"string", "comment", "preamble"}:
            yield entry_type, body
        position = end


def _split_top_level(value: str, delimiter: str) -> list[str]:
    parts: list[str] = []
    depth, quoted, escaped, start = 0, False, False, 0
    for index, char in enumerate(value):
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"' and depth == 0:
            quoted = not quoted
        elif not quoted and char == "{":
            depth += 1
        elif not quoted and char == "}":
            depth = max(0, depth - 1)
        elif char == delimiter and not quoted and depth == 0:
            parts.append(value[start:index].strip())
            start = index + 1
    parts.append(value[start:].strip())
    return parts


def _bib_value(raw: str, *, preserve_braces: bool = False) -> str | None:
    chunks: list[str] = []
    for part in _split_top_level(raw, "#"):
        part = part.strip().strip(",")
        if len(part) >= 2 and part[0] == "{" and part[-1] == "}":
            part = part[1:-1]
        elif len(part) >= 2 and part[0] == '"' and part[-1] == '"':
            part = part[1:-1]
        elif re.fullmatch(r"[A-Za-z][A-Za-z0-9_:-]*", part):
            # BibTeX string macros cannot safely be guessed or expanded unless
            # their definitions are parsed. Omit the whole field instead.
            return None
        chunks.append(part)
    value = "".join(chunks)
    value = re.sub(r"\\([%&_#$])", r"\1", value)
    value = value.replace("~", " ")
    if not preserve_braces:
        value = value.replace("{", "").replace("}", "")
    return " ".join(value.split())


def _parse_bibtex(content: str) -> list[tuple[str, dict[str, list[str]]]]:
    result: list[tuple[str, dict[str, list[str]]]] = []
    for entry_type, body in _bib_entries(content):
        parts = _split_top_level(body, ",")
        fields: dict[str, list[str]] = {}
        for part in parts[1:]:  # First part is the citation key.
            if "=" not in part:
                continue
            key, raw_value = part.split("=", 1)
            field_name = key.strip().casefold()
            value = _bib_value(raw_value, preserve_braces=field_name == "author")
            if value is None:
                fields.setdefault("__warnings__", []).append(
                    f"The BibTeX {key.strip()} field uses a string macro and was omitted."
                )
            else:
                fields[field_name] = [value]
        if fields:
            result.append((entry_type, fields))
    return result


def _first(fields: dict[str, list[str]], *keys: str) -> str:
    for key in keys:
        values = fields.get(key.casefold())
        if values:
            return values[0].strip()
    return ""


def _authors(raw: str) -> list[str]:
    # Preserve imported name spellings; the formatter separately warns about
    # names whose family/given boundary cannot be safely determined.
    names: list[str] = []
    start = depth = 0
    index = 0
    while index < len(raw):
        if raw[index] == "{":
            depth += 1
        elif raw[index] == "}":
            depth = max(0, depth - 1)
        elif (depth == 0 and raw[index:index + 3].casefold() == "and"
              and index > 0 and index + 3 < len(raw)
              and raw[index - 1].isspace() and raw[index + 3].isspace()):
            names.append(raw[start:index].strip())
            start = index + 3
            index += 2
        index += 1
    names.append(raw[start:].strip())
    names = [" ".join(author.strip().strip("{}").split()) for author in names if author]
    return names[:20]


def _year(raw: str) -> int | None:
    match = re.search(r"\b(1[5-9]\d{2}|20\d{2}|2100)\b", raw)
    return int(match.group(1)) if match else None


def _to_item(entry_type: str, fields: dict[str, list[str]]) -> ReferenceImportItem:
    entry_type = entry_type.casefold()
    if entry_type in {"article", "jour"}:
        kind = "journal"
    elif entry_type in {"book", "booklet"}:
        kind = "book"
    elif entry_type in {"inproceedings", "conference", "incollection"}:
        kind = "conference"
    elif entry_type in {"unpublished", "preprint"}:
        kind = "preprint"
    else:
        kind = "other"

    title = _first(fields, "title", "ti", "t1")
    ris_authors = fields.get("au", fields.get("a1", []))
    authors = ([" ".join(author.strip().split()) for author in ris_authors if author.strip()][:20]
               if ris_authors else _authors(_first(fields, "author")))
    year = _year(_first(fields, "year", "py", "y1"))
    start, end = _first(fields, "sp"), _first(fields, "ep")
    pages = _first(fields, "pages") or (f"{start}-{end}" if start and end else start)
    container = _first(fields, "journal", "journaltitle", "booktitle", "jo", "jf", "ja", "t2")
    doi = _first(fields, "doi", "do") or None
    url = _first(fields, "url", "ur")
    warnings = list(fields.get("__warnings__", []))
    if not title:
        warnings.append("No title was found; this item cannot be saved until you add one.")
    if not authors:
        warnings.append("No authors were found; add at least one author before saving.")
    if not year:
        warnings.append("No supported publication year was found.")
    return ReferenceImportItem(
        kind=kind, title=title[:500], authors=authors, year=year,
        container_title=container[:500], volume=_first(fields, "volume", "vl")[:40],
        issue=_first(fields, "number", "issue", "is")[:40], pages=pages[:80],
        article_number=_first(fields, "eid", "m1")[:80],
        publisher=_first(fields, "publisher", "pb")[:300],
        edition=_first(fields, "edition")[:80], doi=doi[:260] if doi else None,
        url=url[:2000], warnings=warnings,
    )
