"""Conservative readable passages with measured word anchors; raw text is untouched."""

import hashlib
import json
import re
from collections import Counter
from typing import Any

from pdfminer import __version__ as miner_version
from pdfplumber import __version__ as plumber_version

from app.modules.documents.figures import figures_on_page, finalize_figures
from app.modules.documents.tables import striped_tables

READER_VERSION = "word-passages-v8:pdfplumber-" + plumber_version + ":pdfminer-" + miner_version


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


def prepare_layouts(pdf: Any) -> list[dict[str, Any]]:
    layouts = []
    total_words = 0
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
        total_words += len(words)
        if len(words) > 12000 or total_words > 200000:
            raise MemoryError
        tables = striped_tables(view, words)
        figures = figures_on_page(view, words, tables)
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
    for layout, entries in zip(layouts, candidates, strict=True):
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
        equations = numbered_equations(layout["words"], table_words | figure_words)
        equation_words = {i for group in equations for i in group}
        for group in equations:
            layout["passages"].append(
                {"text": " ".join(layout["words"][i]["text"] for i in group), "word_indices": group}
            )
        current: list[int] = []
        length = 0
        for i, word in enumerate(layout["words"]):
            if word["margin"] or i in table_words or i in figure_words or i in equation_words:
                if i in equation_words and current:
                    layout["passages"].append(
                        {
                            "text": " ".join(layout["words"][j]["text"] for j in current),
                            "word_indices": current,
                        }
                    )
                    current = []
                    length = 0
                continue
            word_top, _ = flow_bounds(word, layout["rotation"])
            previous_top, previous_bottom = (
                flow_bounds(layout["words"][current[-1]], layout["rotation"])
                if current
                else (word_top, word_top)
            )
            if current and (word_top < previous_top - 0.025 or word_top > previous_bottom + 0.045):
                layout["passages"].append(
                    {
                        "text": " ".join(layout["words"][j]["text"] for j in current),
                        "word_indices": current,
                    }
                )
                current = []
                length = 0
            current.append(i)
            length += len(word["text"]) + 1
            if length >= 700 and (word["text"].endswith((".", "?", "!", ";")) or length >= 1100):
                layout["passages"].append(
                    {
                        "text": " ".join(layout["words"][j]["text"] for j in current),
                        "word_indices": current,
                    }
                )
                current = []
                length = 0
        if current:
            layout["passages"].append(
                {
                    "text": " ".join(layout["words"][j]["text"] for j in current),
                    "word_indices": current,
                }
            )
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
    return layouts
