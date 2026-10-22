"""Conservative readable passages with measured word anchors; raw text is untouched."""

import hashlib
import json
import re
from collections import Counter
from statistics import median
from typing import Any

from pdfminer import __version__ as miner_version
from pdfplumber import __version__ as plumber_version

from app.modules.documents.back_matter import heading_starts as back_matter_starts
from app.modules.documents.back_matter import is_endnote_start
from app.modules.documents.continued_tables import continued_tables
from app.modules.documents.figures import figures_on_page, finalize_figures
from app.modules.documents.front_matter import front_matter
from app.modules.documents.labelled_tables import labelled_tables
from app.modules.documents.links import finalize_links, page_links
from app.modules.documents.quality import assess_page
from app.modules.documents.regression_tables import regression_tables
from app.modules.documents.tables import striped_tables

READER_VERSION = "word-passages-v32:pdfplumber-" + plumber_version + ":pdfminer-" + miner_version


def _reading_order(words: list[dict[str, Any]], rotation: int = 0) -> list[dict[str, Any]]:
    """Return visual reading order, including full-column newspaper layouts.

    pdfplumber's ``use_text_flow`` follows the PDF's content-stream order,
    which is often right-column-first. Detect a strong vertical gutter and
    read complete columns left-to-right, while leaving ordinary single-column
    pages in their measured top-to-bottom order.
    """
    if rotation or len(words) < 16:
        return words
    body_centers = sorted(
        (word["box"][0] + word["box"][2]) / 2
        for word in words
        if word["box"][1] > 0.08 and word["box"][3] < 0.92
    )
    centers = body_centers or sorted((word["box"][0] + word["box"][2]) / 2 for word in words)
    gaps = [(centers[i + 1] - centers[i], i) for i in range(len(centers) - 1)]
    gap, split = max(gaps, default=(0.0, 0))
    if gap < 0.14:
        return words
    threshold = (centers[split] + centers[split + 1]) / 2
    left = [word for word in words if (word["box"][0] + word["box"][2]) / 2 < threshold]
    right = [word for word in words if (word["box"][0] + word["box"][2]) / 2 >= threshold]
    if len(left) < 8 or len(right) < 8:
        return words
    return sorted(left, key=lambda word: (word["box"][1], word["box"][0])) + sorted(
        right, key=lambda word: (word["box"][1], word["box"][0])
    )


def flow_bounds(word: dict[str, Any], rotation: int) -> tuple[float, float]:
    """Compare paragraph gaps along the unrotated reading axis, not canvas y."""
    left, top, right, bottom = word["box"]
    if rotation == 90:
        return 1 - right, 1 - left
    if rotation == 180:
        return 1 - bottom, 1 - top
    if rotation == 270:
        return left, right
    return top, bottom


def section_starts(
    words: list[dict[str, Any]], excluded: set[int], height: float, rotation: int
) -> set[int]:
    """Recognize isolated numbered title lines larger than nearby body text.

    Decimal prose and numeric cells are not headings. This intentionally does
    not claim support for same-size bold-only or unnumbered titles.
    """
    starts: set[int] = set()
    for i, word in enumerate(words):
        if i in excluded or word["margin"] or not re.fullmatch(r"\d+(?:\.\d+){0,3}", word["text"]):
            continue
        top, bottom = flow_bounds(word, rotation)
        if i and abs(flow_bounds(words[i - 1], rotation)[0] - top) * height < 4:
            continue
        line = []
        for j in range(i, min(len(words), i + 30)):
            if (
                j in excluded
                or words[j]["margin"]
                or abs(flow_bounds(words[j], rotation)[0] - top) * height > 4
            ):
                break
            line.append(j)
        title = " ".join(words[j]["text"] for j in line)
        if len(title) > 180 or not re.search(r"[A-Za-z]", title) or title.endswith((".", ";")):
            continue
        neighbours = [
            flow_bounds(words[j], rotation)[1] - flow_bounds(words[j], rotation)[0]
            for j in range(max(0, i - 40), min(len(words), i + 80))
            if j not in excluded and j not in line and not words[j]["margin"]
        ]
        if len(neighbours) >= 8 and bottom - top >= median(neighbours) * 1.1:
            starts.add(i)
    return starts


def numbered_equations(words: list[dict[str, Any]], excluded: set[int]) -> list[list[int]]:
    """Isolate compact equation runs ending with a right-aligned number.

    Preserve PDF token order, including undecodable glyphs; never infer LaTeX.
    This intentionally handles only clear numbered display equations.
    """
    groups = []
    used: set[int] = set()
    for end, word in enumerate(words):
        if end in excluded or word["margin"] or not re.fullmatch(r"\(\d{1,3}\)", word["text"]):
            continue
        if word["box"][0] < 0.8:
            continue
        indices: list[int] = []
        for i in range(end - 1, max(-1, end - 81), -1):
            item = words[i]
            if i in excluded or i in used or item["margin"]:
                break
            if len(item["text"]) > 8 or abs(item["box"][1] - word["box"][1]) > 0.09:
                break
            indices.insert(0, i)
        # Do not absorb preceding short prose (e.g. "a firm:").
        while indices and words[indices[0]]["text"].endswith((":", ".", ";")):
            indices.pop(0)
        equals = any("=" in words[i]["text"] for i in indices)
        math = any(any(0xE000 <= ord(c) <= 0xF8FF for c in words[i]["text"]) for i in indices)
        if len(indices) >= 4 and equals and math:
            # Restrict the start to the mathematical run after the last prose punctuation.
            boundaries = [j for j, i in enumerate(indices) if words[i]["text"].endswith(":")]
            if boundaries:
                indices = indices[boundaries[-1] + 1 :]
            indices.append(end)
            groups.append(indices)
            used.update(indices)
    return groups


def classify_publication_footers(layout: dict[str, Any]) -> None:
    """Keep clearly smaller first-page publication notices out of research evidence."""
    words = layout["words"]
    passages = layout["passages"]
    if not any(p.get("role") == "abstract" for p in passages):
        return
    body_heights = [
        words[i]["box"][3] - words[i]["box"][1]
        for passage in passages
        if passage.get("role", "body") == "body"
        for i in passage["word_indices"]
        if words[i]["box"][1] < 0.9
    ]
    if not body_heights:
        return
    usual_height = median(body_heights)
    for passage in passages:
        if passage.get("role", "body") != "body" or not passage["word_indices"]:
            continue
        positions = [words[i]["box"] for i in passage["word_indices"]]
        if min(box[1] for box in positions) < 0.9:
            continue
        small_print = median(box[3] - box[1] for box in positions) < usual_height * 0.8
        publication_notice = re.search(
            r"\b(?:copyright|creative commons|open access article|published by|all rights reserved|issn)\b"
            r"|\b(?:19|20)\d{2};\d{1,4}:\d+",
            passage["text"],
            re.I,
        )
        if small_print and publication_notice:
            passage["role"] = "publication_metadata"


def prepare_layouts(pdf: Any) -> list[dict[str, Any]]:
    layouts = []
    total_words = 0
    total_links = 0
    page_ids = {
        page.page_obj.pageid: n for n, page in enumerate(pdf.pages, 1) if hasattr(page, "page_obj")
    }
    for page in pdf.pages:
        # pdfplumber uses rotated, top-origin boxes. PDF.js renders the CropBox.
        crop = page.cropbox or page.bbox
        view = page.crop(crop, strict=False)
        x, y, right, bottom = view.bbox
        width, height = right - x, bottom - y
        if width <= 0 or height <= 0:
            raise ValueError("Invalid page box")
        words = []
        # With text-flow extraction pdfplumber uses char_dir even for rotated glyphs.
        # Keep visual boxes in rotated CropBox space, but tokenize in text direction.
        line_dir, char_dir = {90: ("ltr", "ttb"), 180: ("btt", "rtl"), 270: ("rtl", "btt")}.get(
            page.rotation or 0, ("ttb", "ltr")
        )
        for item in view.extract_words(
            use_text_flow=True,
            expand_ligatures=True,
            x_tolerance_ratio=0.15,
            line_dir=line_dir,
            char_dir=char_dir,
        ):
            text = (
                item["text"]
                .replace("\x00", "")
                .replace("\u00ad", "")
                .replace("\u00a0", " ")
                .strip()
            )
            if not text:
                continue
            if len(text) > 2000:
                raise MemoryError
            box = [
                max(0.0, min(1.0, (item["x0"] - x) / width)),
                max(0.0, min(1.0, (item["top"] - y) / height)),
                max(0.0, min(1.0, (item["x1"] - x) / width)),
                max(0.0, min(1.0, (item["bottom"] - y) / height)),
            ]
            if box[0] >= box[2] or box[1] >= box[3]:
                continue
            words.append({"text": text, "box": [round(v, 6) for v in box], "margin": False})
        words = _reading_order(words, page.rotation or 0)
        total_words += len(words)
        if len(words) > 12000 or total_words > 200000:
            raise MemoryError
        tables = striped_tables(view, words)
        tables += labelled_tables(view, words, tables)
        tables += continued_tables(view, words, tables)
        tables += regression_tables(view, words, tables)
        figures = figures_on_page(view, words, tables)
        links = page_links(view, words, page_ids, len(pdf.pages))
        total_links += len(links)
        if total_links > 5000:
            raise MemoryError
        layouts.append(
            {
                "version": READER_VERSION,
                "width": width,
                "height": height,
                "rotation": page.rotation or 0,
                "words": words,
                "passages": [],
                "tables": tables,
                "figures": figures,
                "links": links,
                "excluded_margin_text": [],
            }
        )
        page.close()
    # Only recurring text at the page edge is excluded from readable/search passages.
    # No arbitrary dehyphenation, spelling repair, number conversion or AI rewriting.
    signatures: Counter[str] = Counter()
    candidates = []
    for layout in layouts:
        groups: dict[tuple[str, int], list[int]] = {}
        for i, word in enumerate(layout["words"]):
            if word["box"][0] > 0.95:
                groups.setdefault(("right", 0), []).append(i)
            elif word["box"][2] < 0.05:
                groups.setdefault(("left", 0), []).append(i)
            elif word["box"][1] < 0.06 or word["box"][3] > 0.94:
                groups.setdefault(("horizontal", round(word["box"][1] * 100)), []).append(i)
        entries = []
        for indices in groups.values():
            text = " ".join(layout["words"][i]["text"] for i in indices)
            signature = re.sub(r"\s+", "", re.sub(r"\d+", "#", text.casefold()))
            entries.append((signature, indices, text))
        signatures.update({entry[0] for entry in entries})
        candidates.append(entries)
    back_role = "body"
    for page_index, (layout, entries) in enumerate(zip(layouts, candidates, strict=True)):
        for signature, indices, text in entries:
            if signatures[signature] >= max(3, len(layouts) * 0.4):
                layout["excluded_margin_text"].append(text)
                for i in indices:
                    layout["words"][i]["margin"] = True
        table_words = {
            i
            for table in layout["tables"]
            for row in table["rows"]
            for cell in row
            for i in cell["word_indices"]
        }
        figure_words = {i for figure in layout["figures"] for i in figure["caption_word_indices"]}
        for i, word in enumerate(layout["words"]):
            cx, cy = (word["box"][0] + word["box"][2]) / 2, (word["box"][1] + word["box"][3]) / 2
            if any(
                f["box"] and f["box"][0] <= cx <= f["box"][2] and f["box"][1] <= cy <= f["box"][3]
                for f in layout["figures"]
            ):
                figure_words.add(i)
        front = front_matter(layout["words"], layout["rotation"]) if page_index == 0 else []
        front_words = {i for block in front for i in block["word_indices"]}
        layout["passages"].extend(front)
        equations = numbered_equations(layout["words"], table_words | figure_words | front_words)
        equation_words = {i for group in equations for i in group}
        for group in equations:
            layout["passages"].append(
                {"text": " ".join(layout["words"][i]["text"] for i in group), "word_indices": group}
            )
        heading_starts = section_starts(
            layout["words"],
            table_words | figure_words | equation_words,
            layout["height"],
            layout["rotation"],
        )
        back_headings = back_matter_starts(
            layout["words"], table_words | figure_words | equation_words | front_words,
            layout["rotation"],
        )
        if page_index == 0:
            anchors = [i for i, role in back_headings.items() if role in {
                "acknowledgments", "endnotes", "references",
            }]
            back_headings = {
                i: role for i, role in back_headings.items()
                if anchors and i >= min(anchors)
            }
        current: list[int] = []
        length = 0

        def flush(role: str, page_layout: dict[str, Any] = layout) -> None:
            nonlocal current, length
            if current:
                passage: dict[str, Any] = {
                    "text": " ".join(page_layout["words"][j]["text"] for j in current),
                    "word_indices": current,
                }
                if role != "body":
                    passage["role"] = role
                page_layout["passages"].append(passage)
                current = []
                length = 0

        for i, word in enumerate(layout["words"]):
            if (
                word["margin"]
                or i in table_words
                or i in figure_words
                or i in equation_words
                or i in front_words
            ):
                if (
                    i in equation_words or i in table_words or i in figure_words or i in front_words
                ) and current:
                    flush(back_role)
                continue
            word_top, _ = flow_bounds(word, layout["rotation"])
            previous_top, previous_bottom = (
                flow_bounds(layout["words"][current[-1]], layout["rotation"])
                if current
                else (word_top, word_top)
            )
            caption_start = (
                word["text"] == "TABLE"
                and i + 1 < len(layout["words"])
                and bool(re.fullmatch(r"[A-Za-z]?\d+[a-z]?", layout["words"][i + 1]["text"]))
            )
            if current and (
                caption_start
                or i in heading_starts
                or i in back_headings
                or (back_role == "endnotes" and is_endnote_start(
                    layout["words"], i, table_words | figure_words | equation_words | front_words,
                    layout["rotation"],
                ))
                or word["text"] in {"Notes:", "Note:"}
                or word_top < previous_top - 0.025
                or word_top > previous_bottom + 0.045
            ):
                flush(back_role)
            if i in back_headings:
                back_role = back_headings[i]
            current.append(i)
            length += len(word["text"]) + 1
            if length >= 700 and (word["text"].endswith((".", "?", "!", ";")) or length >= 1100):
                flush(back_role)
        flush(back_role)
        if page_index == 0:
            classify_publication_footers(layout)
    for number, layout in enumerate(layouts, 1):
        for passage in layout["passages"] + [
            cell for table in layout["tables"] for row in table["rows"] for cell in row
        ]:
            content = [
                READER_VERSION,
                number,
                passage["text"],
                [(i, layout["words"][i]["box"]) for i in passage["word_indices"]],
            ]
            passage["id"] = hashlib.sha256(
                json.dumps(content, ensure_ascii=True, separators=(",", ":")).encode()
            ).hexdigest()
    finalize_figures(layouts, READER_VERSION)
    for number, layout in enumerate(layouts, 1):
        finalize_links(layout, number)
        layout["quality"] = assess_page(layout)
    return layouts
