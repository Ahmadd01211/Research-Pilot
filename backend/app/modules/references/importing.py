"""Bounded BibTeX/RIS parsing into reviewable drafts. Nothing here is saved.

The parsers are deliberately small and linear: they read the fields a reference record
stores, report anything they do not understand as a warning, and never guess metadata.
"""

import re
import unicodedata
from dataclasses import dataclass, field

MAX_IMPORT_ENTRIES = 500
MAX_AUTHORS = 20


class ImportSyntaxError(ValueError):
    pass


@dataclass
class Draft:
    label: str
    kind: str = "other"
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    container_title: str = ""
    doi: str = ""
    url: str = ""
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- LaTeX text cleanup

_ACCENTS = {"`": "\u0300", "'": "\u0301", "^": "\u0302", '"': "\u0308", "~": "\u0303",
            "=": "\u0304", ".": "\u0307", "c": "\u0327", "v": "\u030c", "u": "\u0306",
            "H": "\u030b", "k": "\u0328"}
_LETTERS = {"ss": "ß", "o": "ø", "O": "Ø", "ae": "æ", "AE": "Æ", "oe": "œ", "OE": "Œ",
            "aa": "å", "AA": "Å", "l": "ł", "L": "Ł"}
_STYLE_COMMANDS = r"emph|textit|textbf|textsc|textrm|texttt|textsf|textup|mathrm|mathit|mbox"
_LBRACE, _RBRACE = "\x00", "\x01"


def _accent(match: re.Match[str]) -> str:
    return unicodedata.normalize("NFC", (match.group(2) or match.group(3)) + _ACCENTS[match.group(1)])


def latex_text(raw: str, warnings: list[str], label: str) -> str:
    """Convert common BibTeX LaTeX markup to plain Unicode; keep unknown commands visible."""
    text = re.sub(r"\{?\\([ij])\}?(?![A-Za-z])", r"\1", raw)
    text = re.sub(r"\\([`'^\"~=.])\s*(?:\{\s*([A-Za-z])\s*\}|([A-Za-z]))", _accent, text)
    text = re.sub(r"\\([cvuHk])(?:\s*\{\s*([A-Za-z])\s*\}|\s+([A-Za-z]))", _accent, text)
    text = re.sub(r"\\(ss|ae|AE|oe|OE|aa|AA|o|O|l|L)(?![A-Za-z])\s*",
                  lambda m: _LETTERS[m.group(1)], text)
    text = text.replace(r"\{", _LBRACE).replace(r"\}", _RBRACE)
    text = re.sub(r"\\([&%$#_])", r"\1", text)
    text = re.sub(rf"\\(?:{_STYLE_COMMANDS})(?![A-Za-z])\s*", "", text)
    text = text.replace("---", "\u2014").replace("--", "\u2013").replace("~", " ")
    text = text.replace("{", "").replace("}", "")
    text = text.replace(_LBRACE, "{").replace(_RBRACE, "}")
    unknown = sorted(set(re.findall(r"\\[A-Za-z]+", text)))
    if unknown:
        warnings.append(f"{label}: LaTeX {', '.join(unknown[:5])} was kept as text. Review the wording.")
    return unicodedata.normalize("NFC", " ".join(text.split()))


# ---------------------------------------------------------------------- BibTeX

_MONTHS = {name: str(index) for index, name in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
_BIBTEX_KINDS = {"article": "journal", "book": "book", "inproceedings": "conference",
                 "conference": "conference", "proceedings": "conference",
                 "unpublished": "preprint"}


class _Reader:
    def __init__(self, text: str) -> None:
        self.text, self.pos = text, 0

    def line(self) -> int:
        return self.text.count("\n", 0, self.pos) + 1

    def fail(self, message: str) -> ImportSyntaxError:
        return ImportSyntaxError(f"BibTeX line {self.line()}: {message}")

    def skip_space(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def peek(self) -> str:
        self.skip_space()
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def expect(self, char: str) -> None:
        if self.peek() != char:
            raise self.fail(f"expected “{char}”")
        self.pos += 1

    def name(self) -> str:
        self.skip_space()
        match = re.compile(r"[^\s\"#%'(),={}]+").match(self.text, self.pos)
        if not match:
            raise self.fail("expected a name")
        self.pos = match.end()
        return match.group()

    def balanced(self, close: str) -> str:
        """Read up to the delimiter that closes the current group, tracking brace depth."""
        start, depth = self.pos, 0
        while self.pos < len(self.text):
            char = self.text[self.pos]
            if char == "\\":
                self.pos += 2
                continue
            if char == "{":
                depth += 1
            elif char == "}" and depth > 0:
                depth -= 1
            elif char == close and depth == 0:
                self.pos += 1
                return self.text[start:self.pos - 1]
            elif char == "}":
                raise self.fail("unbalanced “}”")
            self.pos += 1
        raise self.fail("a value or entry is not closed")

    def value(self, macros: dict[str, str], warnings: list[str], label: str) -> str:
        parts = []
        while True:
            char = self.peek()
            if char == "{":
                self.pos += 1
                parts.append(self.balanced("}"))
            elif char == '"':
                self.pos += 1
                parts.append(self.balanced('"'))
            elif char.isdigit():
                match = re.compile(r"\d+").match(self.text, self.pos)
                assert match is not None
                self.pos = match.end()
                parts.append(match.group())
            else:
                macro = self.name().casefold()
                if macro in macros:
                    parts.append(macros[macro])
                else:
                    warnings.append(f"{label}: undefined BibTeX string “{macro}” was left empty.")
            if self.peek() != "#":
                return "".join(parts)
            self.pos += 1


def _split_top(raw: str, pattern: str) -> list[str]:
    """Split on a word separator only outside braces, so {Barnes and Noble} stays whole."""
    pieces, depth, start = [], 0, 0
    separator = re.compile(pattern, re.I)
    index = 0
    while index < len(raw):
        if raw[index] == "{":
            depth += 1
        elif raw[index] == "}":
            depth = max(0, depth - 1)
        elif depth == 0 and (match := separator.match(raw, index)):
            pieces.append(raw[start:index])
            index = start = match.end()
            continue
        index += 1
    pieces.append(raw[start:])
    return [piece.strip() for piece in pieces if piece.strip()]


def _wrapped(raw: str) -> bool:
    """True when one outer brace group spans the whole value, e.g. {World Health Organization}."""
    depth = 0
    for index, char in enumerate(raw):
        depth += {"{": 1, "}": -1}.get(char, 0)
        if depth == 0:
            return index == len(raw) - 1 and index > 0
    return False


def _plain_id(raw: str) -> str:
    """DOIs and URLs only lose BibTeX escapes and braces; no typographic conversion."""
    return re.sub(r"\\([&%$#_~])", r"\1", raw).replace("{", "").replace("}", "").strip()


def _bibtex_name(raw: str, warnings: list[str], label: str) -> str:
    """Apply BibTeX's own "First von Last" rule; braced names stay as organisations."""
    if _wrapped(raw):
        return latex_text(raw, warnings, label)
    if "," in raw:
        return ", ".join(latex_text(part, warnings, label) for part in raw.split(",", 1))
    tokens = _split_top(raw, r"\s+")
    if len(tokens) == 1:
        return latex_text(tokens[0], warnings, label)
    plain = [latex_text(token, warnings, label) for token in tokens]
    von = next((index for index, (token, word) in enumerate(zip(tokens[:-1], plain[:-1], strict=True))
                if index > 0 and not token.startswith("{") and word[:1].islower()), None)
    split = von if von is not None else len(tokens) - 1
    return f"{' '.join(plain[split:])}, {' '.join(plain[:split])}"


def parse_bibtex(text: str) -> list[Draft]:
    reader, macros = _Reader(text), dict(_MONTHS)
    drafts: list[Draft] = []
    while (at := text.find("@", reader.pos)) != -1:
        reader.pos = at + 1
        entry_type = reader.name().casefold()
        opener = reader.peek()
        if opener not in "{(":
            raise reader.fail(f"@{entry_type} must be followed by “{{” or “(”")
        reader.pos += 1
        close = "}" if opener == "{" else ")"
        if entry_type in {"comment", "preamble"}:
            reader.balanced(close)
            continue
        label = f"Entry {len(drafts) + 1}"
        warnings: list[str] = []
        fields: dict[str, str] = {}
        if entry_type != "string":
            key = reader.name() if reader.peek() not in {",", close} else ""
            label = key or label
            if reader.peek() == ",":
                reader.pos += 1
            elif reader.peek() != close:
                raise reader.fail("expected “,” after the citation key")
        while reader.peek() not in {close, ""}:
            name = reader.name().casefold()
            reader.expect("=")
            fields[name] = reader.value(macros, warnings, label)
            if reader.peek() == ",":
                reader.pos += 1
        reader.expect(close)
        if entry_type == "string":
            macros.update(fields)
            continue
        if len(drafts) >= MAX_IMPORT_ENTRIES:
            raise ImportSyntaxError(f"The file has more than {MAX_IMPORT_ENTRIES} entries. Split it and import each part.")
        drafts.append(_bibtex_draft(entry_type, label, fields, warnings))
    return drafts


def _bibtex_draft(entry_type: str, label: str, fields: dict[str, str], warnings: list[str]) -> Draft:
    draft = Draft(label=label, warnings=warnings)
    archive = fields.get("archiveprefix", "").casefold()
    draft.kind = _BIBTEX_KINDS.get(entry_type, "preprint" if archive == "arxiv" else "other")
    if entry_type in {"incollection", "inbook"}:
        warnings.append(f"{label}: book chapter imported as Other with the book as its container.")
    draft.title = latex_text(fields.get("title", ""), warnings, label)
    names = _split_top(fields.get("author", ""), r"\s+and\s+")
    if names and names[-1].casefold() == "others":
        names.pop()
        warnings.append(f"{label}: the source lists further authors only as “others”.")
    draft.authors = [_bibtex_name(name, warnings, label) for name in names]
    if not names and fields.get("editor"):
        warnings.append(f"{label}: only editors are listed; add an author or organisation.")
    draft.year = _year(fields.get("year") or fields.get("date", ""), warnings, label)
    container = fields.get("journal") or fields.get("journaltitle") or fields.get("booktitle", "")
    if entry_type in {"misc", "unpublished"} and not container:
        container = fields.get("howpublished", "")
    draft.container_title = "" if draft.kind == "book" else latex_text(container, warnings, label)
    draft.doi = _plain_id(fields.get("doi", ""))
    draft.url = _plain_id(fields.get("url", ""))
    return draft


# ------------------------------------------------------------------------- RIS

_RIS_KINDS = {"JOUR": "journal", "JFULL": "journal", "MGZN": "journal", "BOOK": "book",
              "EBOOK": "book", "EDBOOK": "book", "CONF": "conference", "CPAPER": "conference",
              "UNPB": "preprint", "CHAP": "other", "ECHAP": "other"}
_RIS_LINE = re.compile(r"^([A-Z][A-Z0-9])  ?-(?: (.*))?$")


def parse_ris(text: str) -> list[Draft]:
    drafts: list[Draft] = []
    tags: dict[str, list[str]] | None = None
    last = ""
    for number, line in enumerate(text.lstrip("\ufeff").splitlines(), 1):
        match = _RIS_LINE.match(line.rstrip())
        if not match:
            if tags is not None and last and line.strip():
                tags[last][-1] += " " + line.strip()
            continue
        tag, value = match.group(1), (match.group(2) or "").strip()
        if tag == "TY":
            if tags is not None:
                raise ImportSyntaxError(f"RIS line {number}: a new record starts before ER ends the last one")
            if len(drafts) >= MAX_IMPORT_ENTRIES:
                raise ImportSyntaxError(f"The file has more than {MAX_IMPORT_ENTRIES} entries. Split it and import each part.")
            tags, last = {"TY": [value]}, "TY"
        elif tag == "ER":
            if tags is None:
                raise ImportSyntaxError(f"RIS line {number}: ER appears without a TY record start")
            drafts.append(_ris_draft(tags, len(drafts) + 1))
            tags, last = None, ""
        elif tags is not None:
            tags.setdefault(tag, []).append(value)
            last = tag
    if tags is not None:
        raise ImportSyntaxError("RIS: the last record has no ER line")
    return drafts


def _ris_draft(tags: dict[str, list[str]], index: int) -> Draft:
    def first(*names: str) -> str:
        return next((tags[name][0] for name in names if tags.get(name, [""])[0]), "")

    label = first("ID") or f"Record {index}"
    draft = Draft(label=label)
    code = tags["TY"][0].upper()
    draft.kind = _RIS_KINDS.get(code, "other")
    if code in {"CHAP", "ECHAP"}:
        draft.warnings.append(f"{label}: book chapter imported as Other with the book as its container.")
    draft.title = " ".join(first("TI", "T1", "CT").split())
    draft.authors = [" ".join(name.split()) for tag in ("AU", "A1") for name in tags.get(tag, []) if name.strip()]
    if not draft.authors and (tags.get("A2") or tags.get("ED")):
        draft.warnings.append(f"{label}: only editors are listed; add an author or organisation.")
    draft.year = _year(first("PY", "Y1", "DA"), draft.warnings, label)
    container = first("T2", "JF", "JO", "BT", "J2", "JA")
    draft.container_title = "" if draft.kind == "book" else " ".join(container.split())
    draft.doi = first("DO")
    urls = [url for value in tags.get("UR", []) for url in value.split()]
    if len(urls) > 1:
        draft.warnings.append(f"{label}: {len(urls)} URLs listed; only the first was kept.")
    draft.url = urls[0] if urls else ""
    return draft


def _year(raw: str, warnings: list[str], label: str) -> int | None:
    match = re.search(r"\b(\d{4})\b", raw)
    if not match:
        if raw.strip():
            warnings.append(f"{label}: year “{raw.strip()[:40]}” was not recognised and was left empty.")
        return None
    year = int(match.group(1))
    if not 1500 <= year <= 2100:
        warnings.append(f"{label}: year {year} is outside 1500–2100 and was left empty.")
        return None
    return year
