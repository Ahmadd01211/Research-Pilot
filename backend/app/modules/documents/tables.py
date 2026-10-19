"""Conservative detection of bounded, alternating-shade, two-column tables."""

from typing import Any


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
        stripes.sort(key=lambda r: r["top"])
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
            if stripes[-1]["bottom"]
            <= r["top"]
            <= stripes[-1]["bottom"] + 2 * (stripes[-1]["bottom"] - stripes[-1]["top"])
        ]
        if not lower:
            continue
        top, tail = stripes[0]["top"], min(lower)
        bbox = [(left - x) / width, (top - y) / height, (end - x) / width, (tail - y) / height]
        indices = [
            i
            for i, w in enumerate(words)
            if bbox[0] <= (w["box"][0] + w["box"][2]) / 2 <= bbox[2]
            and bbox[1] <= (w["box"][1] + w["box"][3]) / 2 <= bbox[3]
        ]
        if not indices:
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
        boundaries = sorted({s["top"] for s in stripes} | {s["bottom"] for s in stripes} | {tail})
        rows: list[list[dict[str, Any]]] = []
        for start, finish in zip(boundaries, boundaries[1:], strict=False):
            cells = []
            for leftcol in [True, False]:
                selected = [
                    i
                    for i in indices
                    if start <= y + (words[i]["box"][1] + words[i]["box"][3]) * height / 2 < finish
                    and ((words[i]["box"][0] + words[i]["box"][2]) / 2 < split) == leftcol
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
            if not all(c["word_indices"] for c in cells):
                rows = []
                break
            rows.append(cells)
        if 3 <= len(rows) <= 100:
            result.append({"box": bbox, "rows": rows, "detection": "alternating-shade-with-gutter"})
    return result
