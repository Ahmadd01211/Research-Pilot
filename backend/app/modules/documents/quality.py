"""Deterministic evidence gates, not a universal PDF accuracy/confidence score."""

import re
from typing import Any

from app.modules.documents.hybrid import route_page

QUALITY_VERSION = "evidence-quality-v4"


def assess_page(layout: dict[str, Any]) -> dict[str, Any]:
    words = layout.get("words", [])
    passages = layout.get("passages", [])
    tables = layout.get("tables", [])
    findings: list[dict[str, str]] = []
    blocked_ids: set[str] = set()
    blocked_tables: set[int] = set()
    all_prose = False
    block_page = False

    def issue(code: str, message: str, severity: str, scope: str) -> None:
        if not any(f["code"] == code for f in findings):
            findings.append(
                {"code": code, "message": message, "severity": severity, "scope": scope}
            )

    if not words:
        block_page = True
        issue(
            "no_measured_text",
            "No measured text is available; this page may need OCR.",
            "block",
            "page",
        )
    cells = [c for t in tables for row in t.get("rows", []) for c in row]
    for item in passages + cells:
        indices = item.get("word_indices", [])
        if any(not isinstance(i, int) or not 0 <= i < len(words) for i in indices) or (
            indices and item["text"] != " ".join(words[i]["text"] for i in indices)
        ):
            block_page = True
            issue(
                "invalid_source_anchor",
                "A source anchor does not match its measured text.",
                "block",
                "page",
            )
    if any(
        not 0 <= w["box"][0] < w["box"][2] <= 1 or not 0 <= w["box"][1] < w["box"][3] <= 1
        for w in words
    ):
        block_page = True
        issue("invalid_word_box", "A measured text location is invalid.", "block", "page")
    for index, table in enumerate(tables):
        rows = table.get("rows", [])
        if (
            not rows
            or not rows[0]
            or any(len(row) != len(rows[0]) for row in rows)
            or table.get("detection", "").endswith("ambiguous")
        ):
            blocked_tables.add(index)
            issue(
                "uncertain_table",
                "A table has uncertain columns or inconsistent rows; it is withheld from retrieval.",
                "block",
                "table",
            )
    for i, word in enumerate(words):
        if (
            word["text"] == "TABLE"
            and word["box"][0] < 0.2
            and i + 1 < len(words)
            and re.fullmatch(r"[A-Za-z]?\d+[a-z]?", words[i + 1]["text"])
        ):
            if i and abs(words[i - 1]["box"][1] - word["box"][1]) < 0.003:
                continue
            if not any(
                _table_matches_caption(table, word["box"])
                for table in tables
            ):
                all_prose = True
                issue(
                    "unstructured_table",
                    "A printed table caption has no validated table structure; page prose is withheld from retrieval.",
                    "block",
                    "prose",
                )
    for figure in layout.get("figures", []):
        box = figure.get("box")
        caption_indices = figure.get("caption_word_indices", [])
        if any(not isinstance(i, int) or not 0 <= i < len(words) for i in caption_indices):
            all_prose = True
            issue(
                "invalid_figure_anchor",
                "A figure caption has an invalid measured source anchor.",
                "block",
                "figure",
            )
            continue
        if not _valid_box(box):
            all_prose = True
            issue(
                "uncertain_figure_boundary",
                "A figure boundary is uncertain; page prose is withheld to avoid chart-label contamination.",
                "block",
                "prose",
            )
            continue
        figure_width, figure_height = box[2] - box[0], box[3] - box[1]
        if figure_width * figure_height > 0.45 or (
            figure_width > 0.92 and figure_height > 0.42
        ):
            all_prose = True
            issue(
                "oversized_figure_region",
                "A detected figure covers an unusually large part of the page; structured fallback review is required.",
                "block",
                "figure",
            )
        if caption_indices:
            caption_box = _indices_box(words, caption_indices)
            vertical_gap = max(box[1] - caption_box[3], caption_box[1] - box[3], 0)
            horizontal_overlap = min(box[2], caption_box[2]) - max(box[0], caption_box[0])
            if vertical_gap > 0.22 or horizontal_overlap <= 0:
                all_prose = True
                issue(
                    "misaligned_figure_caption",
                    "A figure and its printed caption are too far apart or do not overlap horizontally.",
                    "block",
                    "figure",
                )
            if _caption_crosses_columns(words, caption_indices):
                all_prose = True
                issue(
                    "caption_crosses_columns",
                    "A figure caption appears to include text from another column.",
                    "block",
                    "figure",
                )
    candidates = [p for p in passages if p.get("role", "body") in {"body", "abstract", "data_availability", "endnotes"}]
    for passage in candidates:
        text = passage["text"]
        if re.search(r"\(cid:\s*\d+\)", text, re.IGNORECASE):
            blocked_ids.add(passage["id"])
            issue(
                "undecoded_font_glyphs",
                "The PDF contains undecoded font glyph codes; affected passages are withheld from retrieval.",
                "block",
                "passage",
            )
        if any(0xE000 <= ord(c) <= 0xF8FF or c == "\ufffd" for c in text):
            blocked_ids.add(passage["id"])
            issue(
                "undecodable_symbols",
                "Undecodable symbols are present; affected passages are withheld.",
                "block",
                "passage",
            )
        tokens = text.split()
        numeric = sum(bool(re.fullmatch(r"[+−–-]?\d[\d.,%*]*", t)) for t in tokens)
        if len(tokens) >= 20 and numeric >= 12 and numeric / len(tokens) > 0.35:
            blocked_ids.add(passage["id"])
            issue(
                "dense_numeric_prose",
                "Dense numeric prose may be an unstructured table; affected passages are withheld.",
                "block",
                "passage",
            )
        if re.search(r"\b(?:DOI:|Received:)", text) and not any(
            p.get("role") == "abstract" for p in passages
        ):
            blocked_ids.add(passage["id"])
            issue(
                "unclassified_front_matter",
                "Possible publication metadata was not separated confidently; affected passages are withheld.",
                "block",
                "passage",
            )
    body_words = [w for w in words if not w.get("margin")]
    if (
        len(body_words) >= 30
        and sum(len(w["text"]) == 1 and w["text"].isalpha() for w in body_words) / len(body_words)
        > 0.45
    ):
        all_prose = True
        issue(
            "fragmented_text",
            "Many isolated characters suggest fragmented extraction; page prose is withheld.",
            "block",
            "prose",
        )
    links = layout.get("links", [])
    if any(link["status"] == "blocked" for link in links):
        issue(
            "blocked_link_action",
            "Unsafe or unsupported link actions are disabled.",
            "warning",
            "links",
        )
    if any(link["status"] == "unresolved" for link in links):
        issue(
            "unresolved_internal_link",
            "Some internal PDF destinations could not be resolved.",
            "warning",
            "links",
        )
    if any(
        link["status"] == "allowed"
        and not link.get("source_ids")
        and (
            not link.get("word_indices")
            or any(not words[i].get("margin") for i in link["word_indices"])
        )
        for link in links
    ):
        issue(
            "unanchored_link",
            "Some link targets have no measured text anchor; inspect the original.",
            "warning",
            "links",
        )
    withheld = len(candidates) if all_prose or block_page else len(blocked_ids)
    eligible = len(candidates) - withheld
    eligible += (
        0
        if block_page
        else sum(len(t.get("rows", [])) for i, t in enumerate(tables) if i not in blocked_tables)
    )
    eligible += 0 if block_page else sum(bool(f.get("caption")) for f in layout.get("figures", []))
    state = (
        "blocked"
        if block_page or (findings and not eligible)
        else "needs_review"
        if findings
        else "checked"
    )
    return {
        "version": QUALITY_VERSION,
        "state": state,
        "findings": findings,
        "block_page": block_page,
        "withhold_prose": all_prose,
        "blocked_passage_ids": sorted(blocked_ids),
        "blocked_table_indices": sorted(blocked_tables),
        "eligible_units": eligible,
        "withheld_passages": withheld,
        "link_count": len(links),
        "hybrid": route_page({"block_page": block_page, "findings": findings}),
    }


def _table_matches_caption(table: dict[str, Any], caption_box: list[float]) -> bool:
    """Associate a validated table with its nearby caption, including caption-inclusive bounds."""
    box = table.get("box")
    rows = table.get("rows", [])
    if (
        not isinstance(box, list)
        or len(box) != 4
        or not rows
        or not rows[0]
        or any(len(row) != len(rows[0]) for row in rows)
        or str(table.get("detection", "")).endswith("ambiguous")
    ):
        return False
    if any(not isinstance(value, (int, float)) for value in box):
        return False
    caption_left, caption_top, caption_right, caption_bottom = caption_box
    table_left, table_top, table_right, table_bottom = box
    if not (0 <= table_left < table_right <= 1 and 0 <= table_top < table_bottom <= 1):
        return False
    horizontal_overlap = min(caption_right, table_right) > max(caption_left, table_left)
    near_caption = table_top - caption_bottom < 0.13 and caption_top - table_bottom < 0.13
    return bool(horizontal_overlap and near_caption)


def _valid_box(value: object) -> bool:
    return bool(
        isinstance(value, list)
        and len(value) == 4
        and all(isinstance(item, (int, float)) for item in value)
        and 0 <= value[0] < value[2] <= 1
        and 0 <= value[1] < value[3] <= 1
    )


def _indices_box(words: list[dict[str, Any]], indices: list[int]) -> list[float]:
    return [
        min(words[i]["box"][0] for i in indices),
        min(words[i]["box"][1] for i in indices),
        max(words[i]["box"][2] for i in indices),
        max(words[i]["box"][3] for i in indices),
    ]


def _caption_crosses_columns(words: list[dict[str, Any]], indices: list[int]) -> bool:
    lines: dict[float, list[int]] = {}
    for index in indices:
        lines.setdefault(round(words[index]["box"][1], 3), []).append(index)
    for line in lines.values():
        ordered = sorted(line, key=lambda i: words[i]["box"][0])
        if any(
            words[right]["box"][0] - words[left]["box"][2] > 0.12
            for left, right in zip(ordered, ordered[1:], strict=False)
        ):
            return True
    return False
