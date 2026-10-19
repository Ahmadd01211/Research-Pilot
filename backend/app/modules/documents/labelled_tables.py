"""Captioned, shaded-header tables with aligned unnumbered numeric columns."""

import re
from typing import Any

NUMBER = re.compile(r"^[+−–-]?(?:[0-9]+(?:[.,][0-9]+)*[%*]*|[−–-])$")


def labelled_tables(
    view: Any, words: list[dict[str, Any]], existing: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    x, y, right, bottom = view.bbox
    width, height = right - x, bottom - y
    result: list[dict[str, Any]] = []
    for rect in getattr(view, "rects", []):
        if (
            rect["x1"] - rect["x0"] < width * 0.55
            or not 20 < rect["bottom"] - rect["top"] < height * 0.12
        ):
            continue
        left, end = (rect["x0"] - x) / width, (rect["x1"] - x) / width
        top, header_bottom = (rect["top"] - y) / height, (rect["bottom"] - y) / height
        if any(
            t["box"][0] < end and t["box"][2] > left and t["box"][1] <= top <= t["box"][3]
            for t in existing + result
        ):
            continue
        caption = " ".join(
            w["text"]
            for w in words
            if top - 0.06 <= w["box"][1] < top and left - 0.001 <= w["box"][0] < end
        )
        if not re.search(r"\bTABLE\s+[A-Za-z0-9]", caption, re.IGNORECASE):
            continue
        lines: list[list[int]] = []
        indices = [
            i
            for i, w in enumerate(words)
            if not w["margin"]
            and left - 0.001 <= w["box"][0]
            and w["box"][2] <= end + 0.001
            and top <= (w["box"][1] + w["box"][3]) / 2 < 0.94
        ]
        for i in sorted(indices, key=lambda j: (words[j]["box"][1] + words[j]["box"][3]) / 2):
            cy = (words[i]["box"][1] + words[i]["box"][3]) / 2
            if (
                lines
                and abs(cy - (words[lines[-1][0]]["box"][1] + words[lines[-1][0]]["box"][3]) / 2)
                * height
                <= 3
            ):
                lines[-1].append(i)
            else:
                lines.append([i])
        for line in lines:
            line.sort(key=lambda i: words[i]["box"][0])
        header_lines = [
            line for line in lines if max(words[i]["box"][3] for i in line) <= header_bottom + 0.003
        ]
        if not header_lines:
            continue
        header_line = header_lines[-1]
        leaves = [i for i in header_line if words[i]["box"][0] >= left + (end - left) * 0.4]
        if not 3 <= len(leaves) <= 6 or not all(
            re.fullmatch(r"[A-Za-z][A-Za-z-]*", words[i]["text"]) for i in leaves
        ):
            continue
        if any(
            words[b]["box"][0] - words[a]["box"][2] < 0.025
            for a, b in zip(leaves, leaves[1:], strict=False)
        ):
            continue
        # Parent metric text is above the leaves; numeric summary lines stay separate.
        parents = []
        for line in header_lines[:-1]:
            selected = [i for i in line if words[i]["box"][0] >= words[leaves[0]]["box"][0] - 0.005]
            if (
                selected
                and any(re.search(r"[A-Za-z]", words[i]["text"]) for i in selected)
                and not any(NUMBER.fullmatch(words[i]["text"]) for i in selected)
            ):
                parents = selected
        splits = [words[leaves[0]]["box"][0] - 0.015] + [
            (words[a]["box"][2] + words[b]["box"][0]) / 2
            for a, b in zip(leaves, leaves[1:], strict=False)
        ]

        def cell(ids: list[int]) -> dict[str, Any]:
            return {"text": " ".join(words[i]["text"] for i in ids), "word_indices": ids}

        rows = [[cell([])] + [cell(parents + [leaf]) for leaf in leaves]]
        count = 0
        ambiguous = False
        pending: list[int] = []
        for line in lines[lines.index(header_line) + 1 :]:
            groups: list[list[int]] = [[] for _ in range(len(leaves) + 1)]
            for i in line:
                center = (words[i]["box"][0] + words[i]["box"][2]) / 2
                col = sum(center >= split for split in splits)
                groups[col].append(i)
            label = " ".join(words[i]["text"] for i in groups[0])
            numeric = all(
                len(ids) == 1 and NUMBER.fullmatch(words[ids[0]]["text"]) for ids in groups[1:]
            )
            if (
                not any(groups[1:])
                and label
                and (re.match(r"^[A-Z]\.", label) or label.startswith(("“", '"')))
            ):
                pending = line
                continue
            right_words = [i for group in groups[1:] for i in group]
            if not groups[0] or (
                not numeric
                and not (
                    right_words and all(NUMBER.fullmatch(words[i]["text"]) for i in right_words)
                )
            ):
                break
            ambiguous |= not numeric
            if pending:
                rows.append([cell(pending)] + [cell([]) for _ in leaves])
                pending = []
            ambiguous |= any(
                words[i]["box"][0] < split < words[i]["box"][2] for split in splits for i in line
            )
            rows.append([cell(ids) for ids in groups])
            count += 1
        if count < 3:
            continue
        used = [i for row in rows for c in row for i in c["word_indices"]]
        result.append(
            {
                "box": [
                    left,
                    min(words[i]["box"][1] for i in used),
                    end,
                    max(words[i]["box"][3] for i in used),
                ],
                "rows": rows,
                "detection": "aligned-labelled-ambiguous"
                if ambiguous
                else "aligned-labelled-columns",
            }
        )
    return result
