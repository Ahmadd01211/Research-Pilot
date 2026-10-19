"""Conservative readable passages with measured word anchors; raw text is untouched."""

import hashlib
import json
import re
from collections import Counter
from typing import Any

from pdfminer import __version__ as miner_version
from pdfplumber import __version__ as plumber_version

from app.modules.documents.tables import striped_tables

READER_VERSION = "word-passages-v4:pdfplumber-" + plumber_version + ":pdfminer-" + miner_version


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
        for item in view.extract_words(
            use_text_flow=True, expand_ligatures=True, x_tolerance_ratio=0.15
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
        layouts.append(
            {
                "version": READER_VERSION,
                "width": width,
                "height": height,
                "rotation": page.rotation or 0,
                "words": words,
                "passages": [],
                "tables": striped_tables(view, words),
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
        current: list[int] = []
        length = 0
        for i, word in enumerate(layout["words"]):
            if word["margin"] or i in table_words:
                continue
            if current and (
                word["box"][1] < layout["words"][current[-1]]["box"][1] - 0.025
                or word["box"][1] > layout["words"][current[-1]]["box"][3] + 0.045
            ):
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
    return layouts
