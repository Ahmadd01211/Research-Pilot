"""Figure evidence from printed captions and embedded-image bounds, never vision inference."""

import hashlib
import json
import re
from typing import Any

CAPTION = re.compile(
    r"^(?:(?:FIGURE|FIG\.?)\s+([A-Z]?\d+[a-z]?)\b|(?:Figure|Fig\.)\s+([A-Z]?\d+[a-z]?)[.:])"
)


def figures_on_page(
    view: Any, words: list[dict[str, Any]], tables: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    left, top, right, bottom = view.bbox
    width, height = right - left, bottom - top
    lines: list[list[int]] = []
    for i in sorted(
        range(len(words)), key=lambda i: (sum(words[i]["box"][1::2]) / 2, words[i]["box"][0])
    ):
        word = words[i]
        if word["box"][0] > 0.95 or word["box"][2] < 0.05:
            continue
        center = sum(word["box"][1::2]) / 2
        if lines and abs(center - sum(words[lines[-1][0]]["box"][1::2]) / 2) * height <= 3:
            lines[-1].append(i)
        else:
            lines.append([i])
    for line in lines:
        line.sort(key=lambda i: words[i]["box"][0])
    captions: list[dict[str, Any]] = []
    for n, line in enumerate(lines):
        text = " ".join(words[i]["text"] for i in line)
        match = CAPTION.match(text)
        if not match:
            continue
        selected = list(line)
        last = max(words[i]["box"][3] for i in line)
        for following in lines[n + 1 :]:
            first = min(words[i]["box"][1] for i in following)
            next_text = " ".join(words[i]["text"] for i in following)
            if (
                (first - last) * height > 6
                or CAPTION.match(next_text)
                or next_text.startswith(("TABLE ", "Table "))
                or first > 0.95
            ):
                break
            if len(" ".join(words[i]["text"] for i in selected + following)) > 5000:
                break
            selected.extend(following)
            last = max(words[i]["box"][3] for i in following)
        captions.append(
            {
                "label": "Figure " + (match.group(1) or match.group(2)),
                "caption": " ".join(words[i]["text"] for i in selected),
                "caption_word_indices": selected,
                "box": None,
                "detection": "source_page",
                "related_passages": [],
            }
        )
        if len(captions) >= 12:
            break
    images = []
    for image in getattr(view, "images", []):
        box = [
            max(0.0, (image["x0"] - left) / width),
            max(0.0, (image["top"] - top) / height),
            min(1.0, (image["x1"] - left) / width),
            min(1.0, (image["bottom"] - top) / height),
        ]
        if (
            (box[2] - box[0]) * (box[3] - box[1]) < 0.02
            or box[2] - box[0] < 0.15
            or box[3] - box[1] < 0.08
        ):
            continue  # Logos and page decoration are not evidence figures.
        if any(
            box[0] < t["box"][2]
            and box[2] > t["box"][0]
            and box[1] < t["box"][3]
            and box[3] > t["box"][1]
            for t in tables
        ):
            continue
        images.append(box)
        if len(images) >= 12:
            break
    used = set()
    for caption in captions:
        caption_top = min(words[i]["box"][1] for i in caption["caption_word_indices"])
        caption_bottom = max(words[i]["box"][3] for i in caption["caption_word_indices"])
        candidates = sorted(
            (
                (
                    max(box[1] - caption_bottom, caption_top - box[3], 0),
                    j,
                    box,
                )
                for j, box in enumerate(images)
                if j not in used
            ),
            key=lambda item: item[0],
        )
        # Captions may be above or below vector/raster figures. Require a unique
        # nearby image; ambiguous layouts retain the source-page fallback.
        if candidates and (
            candidates[0][0] < 0.12
            and (len(candidates) == 1 or candidates[1][0] - candidates[0][0] > 0.03)
        ):
            _, j, box = candidates[0]
            caption["box"] = box
            caption["detection"] = "embedded_image"
            used.add(j)
    for j, box in enumerate(images):
        if j not in used:
            captions.append(
                {
                    "label": None,
                    "caption": None,
                    "caption_word_indices": [],
                    "box": box,
                    "detection": "embedded_image",
                    "related_passages": [],
                }
            )
    return captions[:12]


def finalize_figures(layouts: list[dict[str, Any]], version: str) -> None:
    for number, layout in enumerate(layouts, 1):
        for figure in layout["figures"]:
            content = [
                version,
                number,
                figure["caption"],
                figure["box"],
                figure["caption_word_indices"],
            ]
            figure["id"] = hashlib.sha256(
                json.dumps(content, separators=(",", ":"), ensure_ascii=True).encode()
            ).hexdigest()
            if not figure["label"]:
                figure["label"] = f"Visual evidence on PDF page {number}"
            if not figure["caption"]:
                continue
            label = figure["label"].split()[-1]
            reference = re.compile(
                r"\b(?:Figure|Fig\.?)\s+" + re.escape(label) + r"(?![\w])", re.IGNORECASE
            )
            for other_page, other in enumerate(layouts, 1):
                for passage in other["passages"]:
                    if reference.search(passage["text"]):
                        figure["related_passages"].append(
                            {
                                "page_number": other_page,
                                "passage_id": passage["id"],
                                "text": passage["text"],
                            }
                        )
                        if len(figure["related_passages"]) >= 8:
                            break
                if len(figure["related_passages"]) >= 8:
                    break
