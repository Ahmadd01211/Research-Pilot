"""Conservative geometry-backed section and endnote boundaries for scholarly PDFs."""

import re
from typing import Any

HEADINGS = {
    "ACKNOWLEDGMENTS": "acknowledgments",
    "ACKNOWLEDGEMENTS": "acknowledgments",
    "FUNDING": "funding",
    "FUNDING INFORMATION": "funding",
    "DATA AVAILABILITY": "data_availability",
    "DATA AVAILABILITY STATEMENT": "data_availability",
    "ORCID": "orcid",
    "AUTHOR CONTRIBUTIONS": "author_contributions",
    "CONFLICT OF INTEREST": "conflict_of_interest",
    "CONFLICTS OF INTEREST": "conflict_of_interest",
    "DECLARATION OF INTERESTS": "conflict_of_interest",
    "ETHICS STATEMENT": "ethics_statement",
    "ENDNOTES": "endnotes",
    "REFERENCES": "references",
    "BIBLIOGRAPHY": "references",
}


def heading_starts(words: list[dict[str, Any]], excluded: set[int], rotation: int) -> dict[int, str]:
    """Recognize a short standalone heading at the left edge of a text column."""
    if rotation:
        return {}
    found: dict[int, str] = {}
    for i, word in enumerate(words):
        if i in excluded or word["margin"] or word["box"][0] > 0.25:
            continue
        top = word["box"][1]
        if i > 0 and i - 1 not in excluded and not words[i - 1]["margin"]:
            previous = words[i - 1]
            if abs(previous["box"][1] - top) < 0.006:
                continue
        line = []
        for j in range(i, min(i + 6, len(words))):
            if j in excluded or words[j]["margin"] or abs(words[j]["box"][1] - top) > 0.006:
                break
            line.append(words[j]["text"])
        label = re.sub(r"\s+", " ", " ".join(line).strip().upper().rstrip(":"))
        if label in HEADINGS:
            found[i] = HEADINGS[label]
        elif re.match(r"^APPENDIX\s+[A-Z](?::|\b)", label) or label in {
            "APPENDICES", "SUPPLEMENTARY MATERIAL", "SUPPLEMENTAL MATERIAL",
        }:
            found[i] = "body"
    return found


def is_endnote_start(words: list[dict[str, Any]], index: int,
                     excluded: set[int], rotation: int) -> bool:
    """A small, left-gutter integer immediately preceding note text."""
    if rotation or index in excluded or index + 1 >= len(words):
        return False
    word, following = words[index], words[index + 1]
    return bool(
        re.fullmatch(r"[1-9]\d{0,2}", word["text"])
        and word["box"][0] < 0.16
        and word["box"][2] < 0.2
        and following["box"][0] > word["box"][0]
        and following["box"][0] - word["box"][2] < 0.08
        and abs(following["box"][1] - word["box"][1]) < 0.015
        and not following["margin"]
        and index + 1 not in excluded
    )
