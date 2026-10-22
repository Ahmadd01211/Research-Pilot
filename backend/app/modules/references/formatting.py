"""Limited bibliography previews from stored reference fields; read-only and never invents data.

Rules follow the APA 7 reference examples (apastyle.apa.org), the MLA 9 core elements
(style.mla.org) and Chicago 18 notes-bibliography bibliography entries (chicagomanualofstyle.org).
Fields the record does not hold (volume, issue, pages, publisher, editors, full dates) are
omitted and reported as limitations instead of approximated.

Author convention: "Family, Given" marks a person with a known family/given boundary.
Any other text (no comma, or more than one comma) is kept exactly as entered, which suits
organizations; such names are flagged so a researcher can confirm them.
"""

import unicodedata
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.projects.service import owned as owned_project
from app.modules.references.models import ReferenceRecord
from app.modules.references.schemas import (
    Bibliography,
    BibliographyEntry,
    BibliographySegment,
    CitationStyle,
)
from app.modules.references.service import MAX_REFERENCES, get_settings

STYLE_LABELS: dict[str, str] = {
    "apa7": "APA 7th edition",
    "mla9": "MLA 9th edition",
    "chicago18": "Chicago 18th edition (notes-bibliography, bibliography entries)",
}

COMMON_LIMITATIONS = [
    "Limited preview: check every entry against the official style manual before use.",
    "Volume, issue, pages, publisher, edition, editors, full publication dates and access "
    "dates are not stored, so they are omitted.",
    "Titles keep the capitalization you entered; style-specific title case or sentence "
    "case is not applied automatically.",
    "Authors written as \"Family, Given\" are formatted as people. Other names are shown "
    "exactly as entered, which suits organizations.",
    "Entries are sorted by first author, year, then title using simplified alphabetization.",
]

STYLE_LIMITATIONS: dict[str, list[str]] = {
    "apa7": [
        "Same-author, same-year suffixes (2024a, 2024b) are not added; affected entries "
        "are flagged.",
        "Lists of more than 20 authors and in-press works are not supported.",
    ],
    "mla9": [
        "Only one container is shown; MLA's optional elements and repeated-author dashes "
        "are not added.",
    ],
    "chicago18": [
        "Only bibliography entries are shown; notes and short notes are not generated.",
        "Seven or more authors are shortened to the first three followed by \"et al.\"",
    ],
}


@dataclass(frozen=True)
class Source:
    kind: str
    title: str
    authors: list[str]
    year: int | None
    container_title: str = ""
    doi: str | None = None
    url: str = ""


@dataclass(frozen=True)
class Name:
    raw: str
    family: str | None = None
    given: str = ""

    @property
    def personal(self) -> bool:
        return self.family is not None


@dataclass
class Entry:
    segments: list[tuple[str, bool]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add(self, text: str, italic: bool = False) -> None:
        if text:
            self.segments.append((text, italic))

    @property
    def text(self) -> str:
        return "".join(part for part, _ in self.segments)


def parse_name(raw: str) -> tuple[Name, str | None]:
    """Return the name and an optional warning; never guesses a family/given split."""
    value = " ".join(raw.split())
    parts = [part.strip() for part in value.split(",")]
    if len(parts) == 2 and parts[0]:
        if not parts[1]:
            return Name(value, parts[0], ""), (
                f"Author \"{value}\" has no given name after the comma; only the family "
                "name is shown.")
        return Name(value, parts[0], parts[1]), None
    if len(parts) > 2:
        return Name(value), (
            f"Author \"{value}\" has more than one comma, so it is shown exactly as entered. "
            "Use \"Family, Given\" for a person.")
    return Name(value), (
        f"Author \"{value}\" has no comma, so it is shown exactly as entered. Keep it for an "
        "organization; use \"Family, Given\" for a person.")


def _initials(given: str) -> str:
    words = []
    for word in given.replace(".", ". ").split():
        pieces = [next((c for c in piece if c.isalpha()), "") for piece in word.split("-")]
        if any(pieces):
            words.append("-".join(f"{c.upper()}." for c in pieces if c))
    return " ".join(words)


def _period(text: str) -> str:
    return text if text.endswith((".", "?", "!")) else text + "."


def _link(source: Source) -> str:
    if source.doi:
        return f"https://doi.org/{source.doi}"
    return source.url


def _join_and(names: list[str], conjunction: str) -> str:
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f", {conjunction} " + names[-1]


def _inverted(name: Name) -> str:
    if not name.personal:
        return name.raw
    return f"{name.family}, {name.given}" if name.given else str(name.family)


def _direct(name: Name) -> str:
    if not name.personal:
        return name.raw
    return f"{name.given} {name.family}" if name.given else str(name.family)


def _apa_author(name: Name) -> str:
    if not name.personal:
        return name.raw
    initials = _initials(name.given)
    return f"{name.family}, {initials}" if initials else str(name.family)


def _authors(style: str, names: list[Name]) -> str:
    if style == "apa7":
        return _join_and([_apa_author(name) for name in names], "&")
    if style == "mla9":
        if len(names) >= 3:
            return f"{_inverted(names[0])}, et al"
        return _join_and([_inverted(names[0]), *map(_direct, names[1:])], "and")
    if len(names) > 6:
        return ", ".join([_inverted(names[0]), *map(_direct, names[1:3])]) + ", et al"
    return _join_and([_inverted(names[0]), *map(_direct, names[1:])], "and")


def _apa(source: Source, entry: Entry, authors: str) -> None:
    entry.add(_period(authors) + " ")
    entry.add(f"({source.year if source.year is not None else 'n.d.'}). ")
    entry.add(source.title, source.kind in {"book", "preprint", "other"})
    if source.kind == "preprint":
        entry.add(" [Preprint].")
    elif not source.title.endswith((".", "?", "!")):
        entry.add(".")
    container = source.container_title
    if container and source.kind == "journal":
        entry.add(" ")
        entry.add(container, True)
        entry.add(".")
    elif container and source.kind == "conference":
        entry.add(" In ")
        entry.add(container, True)
        entry.add(".")
    elif container and source.kind in {"preprint", "other"}:
        entry.add(f" {_period(container)}")
    if link := _link(source):
        entry.add(f" {link}")


def _mla(source: Source, entry: Entry, authors: str) -> None:
    entry.add(_period(authors) + " ")
    if source.kind in {"book", "other"}:
        entry.add(source.title, True)
        entry.add("" if source.title.endswith((".", "?", "!")) else ".")
    else:
        entry.add(f"“{_period(source.title)}”")
    tail: list[tuple[str, bool]] = []
    if source.container_title and source.kind != "book":
        tail.append((source.container_title, True))
    if source.year is not None:
        tail.append((str(source.year), False))
    if link := _link(source):
        tail.append((link, False))
    for index, (text, italic) in enumerate(tail):
        entry.add(" " if index == 0 else ", ")
        entry.add(text, italic)
    if tail:
        entry.add(".")


def _chicago(source: Source, entry: Entry, authors: str) -> None:
    entry.add(_period(authors) + " ")
    year = str(source.year) if source.year is not None else "n.d."
    if source.kind in {"book", "other"}:
        entry.add(source.title, True)
        entry.add("" if source.title.endswith((".", "?", "!")) else ".")
        if source.kind == "other" and source.container_title:
            entry.add(f" {source.container_title},")
        entry.add(f" {_period(year)}")
    else:
        entry.add(f"“{_period(source.title)}”")
        container = source.container_title
        if source.kind == "journal" and container:
            entry.add(" ")
            entry.add(container, True)
            entry.add(f" ({year}).")
        elif source.kind == "conference" and container:
            entry.add(" In ")
            entry.add(container, True)
            entry.add(f", {_period(year)}")
        elif source.kind == "preprint":
            entry.add(" Preprint" + (f", {container}" if container else "") + f", {_period(year)}")
        else:
            entry.add(f" {_period(year)}")
    if link := _link(source):
        entry.add(f" {link}.")


def format_source(source: Source, style: str) -> Entry:
    entry = Entry()
    names = []
    for raw in source.authors:
        name, warning = parse_name(raw)
        names.append(name)
        if warning:
            entry.warnings.append(warning)
    if source.year is None:
        entry.warnings.append(
            "Year is missing; shown as “n.d.”." if style != "mla9"
            else "Year is missing, so no date is shown.")
    if not source.container_title and source.kind in {"journal", "conference", "preprint"}:
        label = {"journal": "Journal", "conference": "Proceedings title",
                 "preprint": "Repository or server"}[source.kind]
        entry.warnings.append(f"{label} is missing, so it is omitted.")
    if source.container_title and source.kind == "book":
        entry.warnings.append(
            "The container field is not used for books, and book chapters are not "
            "supported; it is omitted.")
    if not source.doi and not source.url:
        entry.warnings.append("No DOI or URL is stored, so no link is shown.")
    if source.kind == "other":
        entry.warnings.append(
            "“Other” has no specific pattern in this preview; a generic layout is used.")
    if style == "apa7" and len(names) > 20:
        entry.warnings.append("More than 20 authors is not supported; review the author list.")
    authors = _authors(style, names) if names else ""
    {"apa7": _apa, "mla9": _mla, "chicago18": _chicago}[style](source, entry, authors)
    return entry


def _sort_text(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value)
    return "".join(c for c in plain if not unicodedata.combining(c)).casefold()


def _sort_key(source: Source, identifier: UUID) -> tuple[str, int, str, str]:
    names = [parse_name(raw)[0] for raw in source.authors]
    author_key = " ".join(_sort_text(name.family or name.raw) + " " + _sort_text(name.given)
                          for name in names)
    year = source.year if source.year is not None else 0
    return author_key, year, _sort_text(source.title), str(identifier)


def _author_list_key(source: Source) -> str:
    names = [parse_name(raw)[0] for raw in source.authors]
    return "|".join(f"{_sort_text(name.family)},{_sort_text(name.given)}" if name.family is not None
                    else _sort_text(name.raw) for name in names)


def bibliography(db: Session, owner: UUID, project_id: UUID) -> Bibliography:
    owned_project(db, owner, project_id)
    style: CitationStyle = get_settings(db, owner, project_id).style
    records = db.scalars(select(ReferenceRecord).where(
        ReferenceRecord.project_id == project_id, ReferenceRecord.deleted_at.is_(None),
    ).limit(MAX_REFERENCES)).all()
    sources = [(record.id, Source(record.kind, record.title, list(record.authors), record.year,
                                  record.container_title, record.doi, record.url))
               for record in records]
    sources.sort(key=lambda item: _sort_key(item[1], item[0]))
    seen: dict[tuple[str, int | None], int] = {}
    for _, source in sources:
        group = (_author_list_key(source), source.year)
        seen[group] = seen.get(group, 0) + 1
    items = []
    for identifier, source in sources:
        entry = format_source(source, style)
        if style == "apa7" and seen[(_author_list_key(source), source.year)] > 1:
            entry.warnings.append(
                "Another entry has the same authors and year; APA letter suffixes are not "
                "added automatically.")
        items.append(BibliographyEntry(
            reference_id=identifier, text=entry.text, warnings=entry.warnings,
            segments=[BibliographySegment(text=text, italic=italic)
                      for text, italic in entry.segments]))
    return Bibliography(style=style, style_label=STYLE_LABELS[style], preview=True,
                        limitations=COMMON_LIMITATIONS + STYLE_LIMITATIONS[style], items=items)
