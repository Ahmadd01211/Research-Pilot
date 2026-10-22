"""Detect continued tables with repeated numbered headers and aligned numeric rows."""

import re
from typing import Any

from app.modules.documents.labelled_tables import NUMBER

CAPTION = re.compile(r"^TABLE\s+[A-Za-z]?\d+[a-z]?\s+\(Continued\)", re.IGNORECASE)
NUMBERED_HEADER = re.compile(r"^\((\d{1,2})\)$")
CELL_VALUE = re.compile(r"^(?:Yes|No|N/A|NA)$", re.IGNORECASE)


def measured_value(text: str) -> bool:
    return bool(NUMBER.fullmatch(text) or CELL_VALUE.fullmatch(text))


def continued_tables(
    view: Any, words: list[dict[str, Any]], existing: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Use measured repeated headers plus numeric alignment; never infer columns by value count."""
    _x, _y, _right, _bottom = view.bbox
    height = _bottom - _y
    lines: list[list[int]] = []
    for index in sorted(range(len(words)), key=lambda i: (words[i]["box"][1], words[i]["box"][0])):
        if words[index]["margin"] or words[index]["box"][0] > 0.95 or words[index]["box"][2] < 0.05:
            continue
        center = (words[index]["box"][1] + words[index]["box"][3]) / 2
        if lines:
            prior = (words[lines[-1][0]]["box"][1] + words[lines[-1][0]]["box"][3]) / 2
        else:
            prior = center
        if lines and abs(center - prior) * height <= 3:
            lines[-1].append(index)
        else:
            lines.append([index])
    for line in lines:
        line.sort(key=lambda i: words[i]["box"][0])

    result: list[dict[str, Any]] = []
    for caption_pos, caption_line in enumerate(lines):
        caption_text = " ".join(words[i]["text"] for i in caption_line)
        if not CAPTION.match(caption_text):
            continue
        caption_top = min(words[i]["box"][1] for i in caption_line)
        caption_end = max(words[i]["box"][3] for i in caption_line)
        header_pos = None
        headers: list[int] = []
        for pos in range(caption_pos + 1, min(len(lines), caption_pos + 5)):
            if min(words[i]["box"][1] for i in lines[pos]) - caption_end > 0.065:
                break
            current = sorted(
                (i for i in lines[pos] if NUMBERED_HEADER.fullmatch(words[i]["text"])),
                key=lambda i: words[i]["box"][0],
            )
            if 2 <= len(current) <= 8 and [words[i]["text"] for i in current] == [
                f"({n})" for n in range(1, len(current) + 1)
            ]:
                header_pos, headers = pos, current
                break
        if header_pos is None:
            continue

        centers = [(words[i]["box"][0] + words[i]["box"][2]) / 2 for i in headers]
        splits = [centers[0] - 0.035] + [
            (a + b) / 2 for a, b in zip(centers, centers[1:], strict=False)
        ]
        names: list[list[int]] = [[] for _ in headers]
        row_header: list[int] = []
        data_start = header_pos + 1
        for pos in range(header_pos + 1, min(len(lines), header_pos + 5)):
            line = lines[pos]
            text = " ".join(words[i]["text"] for i in line)
            if text.startswith(("Notes:", "Note:", "Abbreviation:")):
                break
            assigned: list[list[int]] = [[] for _ in range(len(headers) + 1)]
            for index in line:
                center = (words[index]["box"][0] + words[index]["box"][2]) / 2
                col = sum(center >= split for split in splits)
                assigned[col].append(index)
            if assigned[0] and all(
                len(group) == 1 and measured_value(words[group[0]]["text"])
                for group in assigned[1:]
            ):
                data_start = pos
                break
            if any(assigned):
                row_header.extend(assigned[0])
                for column, indices in enumerate(assigned[1:]):
                    names[column].extend(indices)
                data_start = pos + 1

        header: list[dict[str, Any]] = [{"text": " ".join(words[i]["text"] for i in row_header), "word_indices": row_header}]
        for number, indices in zip(headers, names, strict=True):
            label = " ".join([words[number]["text"], *(words[i]["text"] for i in indices)])
            header.append({"text": label, "word_indices": [number, *indices]})

        rows: list[list[dict[str, Any]]] = [header]
        used: list[int] = []
        for line in lines[data_start:]:
            text = " ".join(words[i]["text"] for i in line)
            if text.startswith(("Notes:", "Note:", "Abbreviation:")):
                break
            groups: list[list[int]] = [[] for _ in range(len(headers) + 1)]
            for index in line:
                center = (words[index]["box"][0] + words[index]["box"][2]) / 2
                col = sum(center >= split for split in splits)
                groups[col].append(index)
            valid_value = all(
                len(group) == 1 and measured_value(words[group[0]]["text"])
                for group in groups[1:]
            )
            if not groups[0] or not valid_value:
                # Notes and the following body text terminate the table. Other
                # interstitial lines make the candidate too uncertain to trust.
                rows = [header]
                break
            cells = [
                {"text": " ".join(words[i]["text"] for i in group), "word_indices": group}
                for group in groups
            ]
            if any(
                words[i]["box"][0] < split < words[i]["box"][2] for split in splits for i in line
            ):
                rows = [header]
                break
            rows.append(cells)
            used.extend(line)
        if len(rows) < 3:
            continue
        top = min(caption_top, min(words[i]["box"][1] for i in headers))
        left = min(words[i]["box"][0] for i in caption_line)
        right = max(words[i]["box"][2] for i in used)
        bottom = max(words[i]["box"][3] for i in used)
        box = [left, top, right, bottom]
        if any(
            box[0] < table["box"][2]
            and box[2] > table["box"][0]
            and box[1] < table["box"][3]
            and box[3] > table["box"][1]
            for table in existing + result
        ):
            continue
        result.append({"box": box, "rows": rows, "detection": "continued-numbered-columns"})
    return result
