"""Conservative detection of bounded, alternating-shade, two-column tables."""

import re
from typing import Any


def expand_model_subcolumns(
    rows: list[list[dict[str, Any]]], words: list[dict[str, Any]], height: float
) -> tuple[list[list[dict[str, Any]]], str]:
    """Flatten repeated leaf headings while retaining measured parent-word anchors.

    Require matching alphabetic leaf labels in every model group and empty
    vertical gutters through all body rows. Never split by counting numbers.
    """
    specifications = []
    for col, header in enumerate(rows[0][1:], 1):
        indices = header["word_indices"]
        if not indices:
            return rows, "numbered-model-columns"
        baseline = max((words[i]["box"][1] + words[i]["box"][3]) / 2 for i in indices)
        leaves = sorted(
            [
                i
                for i in indices
                if abs((words[i]["box"][1] + words[i]["box"][3]) / 2 - baseline) * height <= 3
            ],
            key=lambda i: words[i]["box"][0],
        )
        if not 2 <= len(leaves) <= 6 or not all(
            re.fullmatch(r"[A-Za-z][A-Za-z-]*", words[i]["text"]) for i in leaves
        ):
            return rows, "numbered-model-columns"
        parent = [i for i in indices if i not in leaves]
        if not parent:
            return rows, "numbered-model-columns"
        specifications.append((col, parent, leaves))
    labels = [[words[i]["text"].casefold() for i in leaves] for _, _, leaves in specifications]
    if len(labels) < 2 or any(label != labels[0] for label in labels[1:]):
        return rows, "numbered-model-columns"
    expanded = [[rows[0][0]]]
    for _ in rows[1:]:
        expanded.append([])
    for row_index, row in enumerate(rows[1:], 1):
        expanded[row_index].append(row[0])
    for col, parent, leaves in specifications:
        splits = [
            (words[a]["box"][2] + words[b]["box"][0]) / 2
            for a, b in zip(leaves, leaves[1:], strict=False)
        ]
        body_indices = [i for row in rows[1:] for i in row[col]["word_indices"]]
        if any(
            words[a]["box"][2] >= words[b]["box"][0]
            for a, b in zip(leaves, leaves[1:], strict=False)
        ) or any(
            words[i]["box"][0] < split < words[i]["box"][2]
            for split in splits
            for i in body_indices
        ):
            return rows, "numbered-model-columns-ambiguous"
        for leaf in leaves:
            selected = parent + [leaf]
            expanded[0].append(
                {"text": " ".join(words[i]["text"] for i in selected), "word_indices": selected}
            )
        edges = [0.0, *splits, 1.0]
        for row_index, row in enumerate(rows[1:], 1):
            for left, right in zip(edges, edges[1:], strict=False):
                selected = [
                    i
                    for i in row[col]["word_indices"]
                    if left <= (words[i]["box"][0] + words[i]["box"][2]) / 2 < right
                ]
                expanded[row_index].append(
                    {"text": " ".join(words[i]["text"] for i in selected), "word_indices": selected}
                )
    return expanded, "numbered-model-subcolumns"


def striped_tables(view: Any, words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    x, y, right, bottom = view.bbox
    width, height = right - x, bottom - y
    rectangles = getattr(view, "rects", [])
    groups: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for rect in rectangles:
        h = rect["bottom"] - rect["top"]
        if rect["x1"] - rect["x0"] > width * 0.55 and 5 < h < height * 0.15:
            groups.setdefault((round(rect["x0"]), round(rect["x1"])), []).append(rect)
    result = []
    for stripes in groups.values():
        left_edge, right_edge = stripes[0]["x0"], stripes[0]["x1"]
        stripes = [
            rect
            for rect in rectangles
            if rect["x0"] >= left_edge - 1
            and abs(rect["x1"] - right_edge) < 1
            and rect["x1"] - rect["x0"] > width * 0.55
            and 5 < rect["bottom"] - rect["top"] < height * 0.15
        ]
        stripes.sort(key=lambda r: r["top"])
        # Publishers often draw adjacent rectangles for coefficients and errors.
        merged: list[dict[str, Any]] = []
        for stripe in stripes:
            if merged and abs(merged[-1]["bottom"] - stripe["top"]) < 0.5:
                merged[-1] = {**merged[-1], "bottom": stripe["bottom"]}
            else:
                merged.append(dict(stripe))
        stripes = merged
        if len(stripes) < 3 or any(
            a["bottom"] >= b["top"] for a, b in zip(stripes, stripes[1:], strict=False)
        ):
            continue
        left, end = stripes[0]["x0"], stripes[0]["x1"]
        rules = [
            r
            for r in rectangles
            if abs(r["x0"] - left) < 2
            and abs(r["x1"] - end) < 2
            and 0 < r["bottom"] - r["top"] <= 2
        ]
        lower = [
            r["top"]
            for r in rules
            if stripes[-1]["bottom"] - 0.5
            <= r["top"]
            <= stripes[-1]["bottom"] + 2 * (stripes[-1]["bottom"] - stripes[-1]["top"])
        ]
        if not lower:
            continue
        top, tail = stripes[0]["top"], max(stripes[-1]["bottom"], min(lower))
        bbox = [(left - x) / width, (top - y) / height, (end - x) / width, (tail - y) / height]
        indices = [
            i
            for i, w in enumerate(words)
            if bbox[0] <= (w["box"][0] + w["box"][2]) / 2 <= bbox[2]
            and bbox[1] <= (w["box"][1] + w["box"][3]) / 2 <= bbox[3]
        ]
        if not indices:
            continue
        # Numbered model headers identify regression-table columns, not equation numbers.
        headers = sorted(
            [
                i
                for i in indices
                if re.fullmatch(r"\(\d{1,2}\)", words[i]["text"])
                and words[i]["box"][1] < bbox[1] + 0.025
            ],
            key=lambda i: words[i]["box"][0],
        )
        caption_words = [
            w["text"]
            for w in words
            if bbox[1] - 0.06 <= w["box"][1] < bbox[1]
            and bbox[0] - 0.001 <= w["box"][0] <= bbox[2] + 0.001
        ]
        has_table_caption = bool(
            re.search(r"\bTABLE\s+[A-Za-z0-9]", " ".join(caption_words), re.IGNORECASE)
        )
        model_table = (
            len(headers) >= 2
            and (len(headers) >= 3 or has_table_caption)
            and [words[i]["text"] for i in headers]
            == [f"({n})" for n in range(1, len(headers) + 1)]
        )
        splits: list[float] = []
        if model_table:
            for header in headers:
                edge = words[header]["box"][0]
                candidates = [edge - n / 2000 for n in range(2, 61)]
                gap = next(
                    (
                        v
                        for v in candidates
                        if bbox[0] < v < bbox[2]
                        and not any(words[i]["box"][0] < v < words[i]["box"][2] for i in indices)
                    ),
                    None,
                )
                if gap is None:
                    splits = []
                    break
                splits.append(gap)
            if len(splits) != len(headers) or splits != sorted(set(splits)):
                continue
        # A measured empty gutter must separate columns; never split through words.
        candidates = [bbox[0] + (bbox[2] - bbox[0]) * n / 200 for n in range(55, 131)]
        gaps = [
            v
            for v in candidates
            if not any(words[i]["box"][0] < v < words[i]["box"][2] for i in indices)
        ]
        if not gaps:
            continue
        split = min(gaps, key=lambda v: abs(v - (bbox[0] + bbox[2]) / 2))
        if not model_table:
            splits = [split]
        boundaries = sorted({s["top"] for s in stripes} | {s["bottom"] for s in stripes} | {tail})
        rows: list[list[dict[str, Any]]] = []
        for start, finish in zip(boundaries, boundaries[1:], strict=False):
            cells = []
            edges = [bbox[0], *splits, bbox[2]]
            for col_left, col_right in zip(edges, edges[1:], strict=False):
                selected = [
                    i
                    for i in indices
                    if start <= y + (words[i]["box"][1] + words[i]["box"][3]) * height / 2 < finish
                    and col_left <= (words[i]["box"][0] + words[i]["box"][2]) / 2 < col_right
                ]
                # Cell text follows its measured lines, including wrapped labels.
                lines: list[list[int]] = []
                for index in sorted(selected, key=lambda i: sum(words[i]["box"][1::2]) / 2):
                    center = sum(words[index]["box"][1::2]) / 2
                    if (
                        lines
                        and abs(center - sum(words[lines[-1][0]]["box"][1::2]) / 2) * height <= 3
                    ):
                        lines[-1].append(index)
                    else:
                        lines.append([index])
                selected = [
                    i for line in lines for i in sorted(line, key=lambda j: words[j]["box"][0])
                ]
                cells.append(
                    {"text": " ".join(words[i]["text"] for i in selected), "word_indices": selected}
                )
            if (not model_table and not all(c["word_indices"] for c in cells)) or not any(
                c["word_indices"] for c in cells
            ):
                rows = []
                break
            rows.append(cells)
        if 3 <= len(rows) <= 100:
            detection = "numbered-model-columns" if model_table else "alternating-shade-with-gutter"
            if model_table:
                rows, detection = expand_model_subcolumns(rows, words, height)
            result.append(
                {
                    "box": bbox,
                    "rows": rows,
                    "detection": detection,
                }
            )
    return result
