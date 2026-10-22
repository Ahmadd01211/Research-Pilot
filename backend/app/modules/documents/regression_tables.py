"""Detect labelled regression tables with numbered model columns and split errors."""

import re
from typing import Any

TABLE_NUMBER = re.compile(r"^[A-Za-z]?\d+[a-z]?$", re.IGNORECASE)
MODEL = re.compile(r"^\((\d{1,2})\)$")
COEFFICIENT = re.compile(r"^[+−–-]?\d+(?:[.,]\d+)*(?:[*†‡]+)?$")
STANDARD_ERROR = re.compile(r"^\([+−–-]?\d+(?:[.,]\d+)+\)$")
END_MARKER = re.compile(r"^(?:Notes?:|Abbreviations?:|\(Continues?\))", re.IGNORECASE)


def regression_tables(
    view: Any, words: list[dict[str, Any]], existing: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Reconstruct regression rows only when caption, numbered columns and alignment agree.

    Model columns are located by the repeated numbered header, never by assuming
    that every row has the same number of observed values. Parent headers are
    retained and coefficient/error lines are joined into the same source cell.
    """
    height = view.bbox[3] - view.bbox[1]
    lines = _lines(words, height)
    tables = []
    for caption_index, line in enumerate(lines):
        caption_ids = _caption_ids(line, words)
        if not caption_ids:
            continue
        caption_top = min(words[i]["box"][1] for i in caption_ids)
        caption_bottom = max(words[i]["box"][3] for i in caption_ids)
        caption_left = min(words[i]["box"][0] for i in caption_ids)
        caption_right = max(words[i]["box"][2] for i in caption_ids)

        marker = _find_model_header(lines, caption_index, caption_bottom, words, height)
        if marker is None:
            continue
        header_line_index, marker_ids = marker
        starts = [words[i]["box"][0] for i in marker_ids]
        gaps = [right - left for left, right in zip(starts, starts[1:], strict=False)]
        if not gaps or min(gaps) < 0.025:
            continue
        # Some publishers center group labels between the model number and the
        # leaf heading. Stay just inside half a column gap so that text still
        # maps unambiguously to its nearest model.
        tolerance = min(0.04, min(gaps) * 0.48)
        body_start = _find_first_data_line(lines, header_line_index + 1, words, starts, tolerance)
        if body_start is None:
            continue
        body_index, _first_values = body_start

        # If an earlier adapter already owns this caption and its measured table,
        # keep that detector's representation to avoid duplicate cells.
        if any(_near_caption(table, caption_top, caption_bottom, caption_left, caption_right) for table in existing):
            continue

        headers: list[list[int]] = [[i] for i in marker_ids]
        body_top = min(words[i]["box"][1] for i in lines[body_index])
        for i, word in enumerate(words):
            if (
                i not in marker_ids
                and
                caption_bottom <= word["box"][1]
                and word["box"][3] <= body_top
                and word["box"][0] >= starts[0] - tolerance
            ):
                column = _column_for(word, starts, tolerance)
                if column is not None:
                    headers[column].append(i)

        label_header_ids = [
            i
            for i in lines[body_index - 1]
            if words[i]["box"][2] < starts[0] - tolerance
            and re.search(r"[A-Za-z]", words[i]["text"])
        ] if body_index > header_line_index + 1 else []
        rows = [[_cell(words, label_header_ids), *[_cell(words, ids) for ids in headers]]]
        min_y = caption_top
        max_y = caption_bottom
        for i in caption_ids + marker_ids + label_header_ids:
            min_y = min(min_y, words[i]["box"][1])
            max_y = max(max_y, words[i]["box"][3])

        pending_label: list[int] = []
        last_coeff_y: float | None = None
        row_count = 0
        malformed = False
        for line in lines[body_index:]:
            line_top = min(words[i]["box"][1] for i in line)
            line_bottom = max(words[i]["box"][3] for i in line)
            text = " ".join(words[i]["text"] for i in line)
            if END_MARKER.match(text):
                break

            label_ids, values, errors, invalid = _classify_line(line, words, starts, tolerance)
            malformed |= invalid
            if invalid:
                break
            if errors and not label_ids:
                if not rows[1:] or last_coeff_y is None or line_top - last_coeff_y > 0.045:
                    malformed = True
                    break
                row = rows[-1]
                for column, ids in enumerate(errors, 1):
                    row[column] = _cell(words, row[column]["word_indices"] + ids)
                last_coeff_y = line_bottom
                max_y = max(max_y, line_bottom)
                continue
            if values and label_ids:
                label_ids = pending_label + label_ids
                pending_label = []
                rows.append([_cell(words, label_ids), *[_cell(words, ids) for ids in values]])
                row_count += 1
                last_coeff_y = line_bottom
                max_y = max(max_y, line_bottom)
                continue
            if label_ids and not values and not errors:
                label = " ".join(words[i]["text"] for i in label_ids)
                if re.match(r"^[A-Z]\.", label):
                    rows.append([_cell(words, label_ids), *[_cell(words, []) for _ in starts]])
                    max_y = max(max_y, line_bottom)
                elif pending_label and line_top - words[pending_label[-1]]["box"][3] > 0.045:
                    break
                else:
                    pending_label.extend(label_ids)
                continue
            if pending_label and line_top - words[pending_label[-1]]["box"][3] > 0.045:
                break

        if malformed or row_count < 3:
            continue
        if pending_label:
            # A trailing note/continuation label is not a data row.
            max_y = max(max_y, max(words[i]["box"][3] for i in pending_label))

        all_ids = [i for row in rows for cell in row for i in cell["word_indices"]]
        if not all_ids:
            continue
        x0 = min(caption_left, *(words[i]["box"][0] for i in all_ids))
        x1 = max(caption_right, *(words[i]["box"][2] for i in all_ids))
        tables.append(
            {
                "box": [x0, min_y, x1, max_y],
                "rows": rows,
                "detection": "regression-model-columns",
            }
        )
    return tables


def _lines(words: list[dict[str, Any]], height: float) -> list[list[int]]:
    lines: list[list[int]] = []
    for index in sorted(
        (
            i
            for i, word in enumerate(words)
            if not word.get("margin")
            # Publisher running matter can share a y-coordinate with a real
            # row, so exclude text measured outside the page's content box.
            and word["box"][0] >= 0.04
            and word["box"][2] <= 0.96
        ),
        key=lambda i: (sum(words[i]["box"][1::2]) / 2, words[i]["box"][0]),
    ):
        center = sum(words[index]["box"][1::2]) / 2
        if lines and abs(center - sum(words[lines[-1][0]]["box"][1::2]) / 2) * height <= 3:
            lines[-1].append(index)
        else:
            lines.append([index])
    for line in lines:
        line.sort(key=lambda i: words[i]["box"][0])
    return lines


def _caption_ids(line: list[int], words: list[dict[str, Any]]) -> list[int]:
    for position, index in enumerate(line[:-1]):
        if words[index]["text"].upper() == "TABLE" and TABLE_NUMBER.fullmatch(
            words[line[position + 1]]["text"].rstrip(".")
        ):
            return line
    return []


def _find_model_header(
    lines: list[list[int]], caption_index: int, caption_bottom: float,
    words: list[dict[str, Any]], height: float,
) -> tuple[int, list[int]] | None:
    for line_index in range(caption_index + 1, len(lines)):
        line = lines[line_index]
        top = min(words[i]["box"][1] for i in line)
        if (top - caption_bottom) * height > 110:
            break
        matched = [
            (i, MODEL.fullmatch(words[i]["text"]))
            for i in line
            if MODEL.fullmatch(words[i]["text"]) is not None
        ]
        matched.sort(key=lambda pair: words[pair[0]]["box"][0])
        markers = [i for i, _match in matched]
        numbers = [int(match.group(1)) for _, match in matched if match is not None]
        if 3 <= len(markers) <= 12 and numbers == list(range(1, len(markers) + 1)):
            return line_index, markers
    return None


def _column_for(word: dict[str, Any], starts: list[float], tolerance: float) -> int | None:
    nearest = min(range(len(starts)), key=lambda column: abs(word["box"][0] - starts[column]))
    return nearest if abs(word["box"][0] - starts[nearest]) <= tolerance else None


def _classify_line(
    line: list[int], words: list[dict[str, Any]], starts: list[float], tolerance: float
) -> tuple[list[int], list[list[int]], list[list[int]], bool]:
    labels: list[int] = []
    values: list[list[int]] = [[] for _ in starts]
    errors: list[list[int]] = [[] for _ in starts]
    invalid = False
    for index in line:
        word = words[index]
        text = word["text"]
        coefficient = bool(COEFFICIENT.fullmatch(text))
        standard_error = bool(STANDARD_ERROR.fullmatch(text))
        if not coefficient and not standard_error:
            if word["box"][0] < starts[0] - tolerance:
                labels.append(index)
            else:
                invalid = True
            continue
        if word["box"][0] < starts[0] - tolerance:
            labels.append(index)
            continue
        column = _column_for(word, starts, tolerance)
        if column is None:
            invalid = True
            continue
        (errors if standard_error else values)[column].append(index)
    if any(values[i] and errors[i] for i in range(len(starts))):
        invalid = True
    return labels, values, errors, invalid


def _find_first_data_line(
    lines: list[list[int]], start: int, words: list[dict[str, Any]],
    starts: list[float], tolerance: float,
) -> tuple[int, list[list[int]]] | None:
    for index in range(start, len(lines)):
        labels, values, errors, invalid = _classify_line(lines[index], words, starts, tolerance)
        if invalid:
            # Multi-line group headers legitimately contain prose above the
            # first data row; alignment validation starts at the first row.
            continue
        if labels and any(values) and not any(errors):
            return index, values
    return None


def _cell(words: list[dict[str, Any]], indices: list[int]) -> dict[str, Any]:
    # Small baseline differences in a single printed row should not reorder
    # labels such as “Owner age (35–54)”.
    ordered = sorted(indices, key=lambda i: (round(words[i]["box"][1], 2), words[i]["box"][0]))
    return {"text": " ".join(words[i]["text"] for i in ordered), "word_indices": ordered}


def _near_caption(
    table: dict[str, Any], top: float, bottom: float, left: float, right: float
) -> bool:
    box = table.get("box")
    return bool(
        box
        and len(box) == 4
        and min(right, box[2]) > max(left, box[0])
        and box[1] - bottom < 0.13
        and top - box[3] < 0.13
    )
