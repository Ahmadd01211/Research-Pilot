"""Figure evidence from printed captions and embedded-image bounds, never vision inference."""

import hashlib
import json
import re
from typing import Any

CAPTION = re.compile(
    r"^(?:FIGURE|FIG\.?|Figure|Fig\.)\s+([A-Z]?\d+[a-z]?)\b(?:[.:]|(?=\s+[A-Z]))",
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
    split_lines: list[list[int]] = []
    for line in lines:
        line.sort(key=lambda i: words[i]["box"][0])
        local: list[int] = []
        for index in line:
            if local and words[index]["box"][0] - words[local[-1]]["box"][2] > 0.08:
                split_lines.append(local)
                local = []
            local.append(index)
        if local:
            split_lines.append(local)
    lines = sorted(
        split_lines,
        key=lambda line: (
            min(words[i]["box"][1] for i in line),
            min(words[i]["box"][0] for i in line),
        ),
    )
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
            selected_left = min(words[i]["box"][0] for i in selected)
            selected_right = max(words[i]["box"][2] for i in selected)
            following_left = min(words[i]["box"][0] for i in following)
            following_right = max(words[i]["box"][2] for i in following)
            next_text = " ".join(words[i]["text"] for i in following)
            same_column = (
                min(selected_right, following_right) - max(selected_left, following_left) > 0.02
                or abs(selected_left - following_left) < 0.05
            )
            if not same_column:
                continue
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
                "label": "Figure " + match.group(1),
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

    # Vector diagrams are stored as drawing commands rather than images. Keep
    # their measured geometry so a caption can be associated with a local
    # shape cluster and previewed as a crop instead of as the complete page.
    vector_boxes: list[list[float]] = []
    for collection in ("rects", "lines", "curves"):
        for shape in getattr(view, collection, []):
            if not all(key in shape for key in ("x0", "x1", "top", "bottom")):
                continue
            box = [
                max(0.0, (shape["x0"] - left) / width),
                max(0.0, (shape["top"] - top) / height),
                min(1.0, (shape["x1"] - left) / width),
                min(1.0, (shape["bottom"] - top) / height),
            ]
            if box[0] >= box[2] or box[1] > box[3]:
                continue
            if box[2] - box[0] > 0.8 or box[3] - box[1] > 0.5:
                continue  # Page frames and decorative rules are not figures.
            vector_boxes.append(box)
            if len(vector_boxes) >= 500:
                break
        if len(vector_boxes) >= 500:
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
        else:
            caption_left = min(words[i]["box"][0] for i in caption["caption_word_indices"])
            caption_right = max(words[i]["box"][2] for i in caption["caption_word_indices"])
            visual_regions = [
                ("image", j, box) for j, box in enumerate(images) if j not in used
            ] + [("vector", j, box) for j, box in enumerate(vector_boxes)]
            measured = []
            for kind, index, box in visual_regions:
                if box[3] <= caption_top:
                    side, distance = "above", caption_top - box[3]
                elif box[1] >= caption_bottom:
                    side, distance = "below", box[1] - caption_bottom
                else:
                    side, distance = "overlap", 0.0
                horizontally_near = not (
                    box[2] < caption_left - 0.18 or box[0] > caption_right + 0.18
                )
                if distance < 0.3 and horizontally_near:
                    measured.append((distance, side, kind, index, box))
            measured.sort(key=lambda item: item[0])
            nearby: list[tuple[float, str, str, int, list[float]]] = []
            if measured:
                nearest, preferred_side = measured[0][0], measured[0][1]
                nearby = [
                    item
                    for item in measured
                    if item[1] == preferred_side and item[0] <= nearest + 0.09
                ]
            enough_geometry = bool(nearby) and (
                any(item[2] == "image" for item in nearby) or len(nearby) >= 2
            )
            if enough_geometry:
                boxes = [item[4] for item in nearby]
                union = [
                    min(box[0] for box in boxes),
                    min(box[1] for box in boxes),
                    max(box[2] for box in boxes),
                    max(box[3] for box in boxes),
                ]
                if union[2] - union[0] >= 0.1 and union[3] - union[1] >= 0.04:
                    caption["box"] = [
                        max(0.0, union[0] - 0.02),
                        max(0.0, union[1] - 0.03),
                        min(1.0, union[2] + 0.02),
                        min(1.0, union[3] + 0.03),
                    ]
                    image_indices = {item[3] for item in nearby if item[2] == "image"}
                    caption["detection"] = (
                        "embedded_image" if image_indices else "vector_graphics"
                    )
                    used.update(image_indices)
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
