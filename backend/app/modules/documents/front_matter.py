"""Conservative first-page classification using explicit abstract/body anchors."""

from typing import Any


def front_matter(words: list[dict[str, Any]], rotation: int) -> list[dict[str, Any]]:
    if rotation:
        return []
    abstracts = [w for w in words if w["text"].casefold().rstrip(":") == "abstract"]
    if len(abstracts) != 1:
        return []
    abstract = abstracts[0]
    ax, ay = abstract["box"][:2]
    introductions = [
        w
        for w in words
        if w["text"].casefold() == "introduction" and w["box"][1] > ay and w["box"][0] < 0.3
    ]
    if not introductions or not any(
        w["text"].casefold() in {"doi:", "received:", "correspondence"} for w in words
    ):
        return []
    body_top = min(w["box"][1] for w in introductions) - 0.003
    candidates = [
        w
        for w in words
        if not w["margin"] and w["box"][3] < ay - 0.03 and any(c.isalpha() for c in w["text"])
    ]
    if not candidates:
        return []
    largest = max(w["box"][3] - w["box"][1] for w in candidates)
    titles = [
        i
        for i, w in enumerate(words)
        if w in candidates and w["box"][3] - w["box"][1] >= largest * 0.88
    ]
    if not titles:
        return []
    title_top = min(words[i]["box"][1] for i in titles)
    title_bottom = max(words[i]["box"][3] for i in titles)
    body_heights = [
        w["box"][3] - w["box"][1]
        for w in words
        if w["box"][0] >= ax and ay < w["box"][1] < body_top
    ]
    if not body_heights or largest < sorted(body_heights)[len(body_heights) // 2] * 1.3:
        return []
    markers = {}
    for metadata_role, label in [("correspondence", "correspondence"), ("funding", "funding")]:
        ys = [
            w["box"][1]
            for w in words
            if w["text"].casefold() == label
            and w["box"][0] < ax
            and ay - 0.025 <= w["box"][1] < body_top
        ]
        if ys:
            markers[metadata_role] = min(ys)
    groups: dict[str, list[int]] = {}
    for i, w in enumerate(words):
        if w["margin"]:
            continue
        cy = (w["box"][1] + w["box"][3]) / 2
        role = None
        if cy < title_top:
            role = "publication_metadata"
        elif title_top <= cy <= title_bottom:
            role = "title"
        elif title_bottom < cy < ay - 0.025:
            role = "authors"
        elif ay - 0.025 <= cy < body_top:
            if w["box"][0] >= ax - 0.005 and cy >= ay:
                role = "abstract"
            elif w["box"][2] < ax - 0.015:
                role = "affiliations"
                for name, top in sorted(markers.items(), key=lambda item: item[1]):
                    if cy >= top:
                        role = name
        if role:
            groups.setdefault(role, []).append(i)
    if "title" not in groups or "abstract" not in groups:
        return []
    return [
        {"role": role, "text": " ".join(words[i]["text"] for i in indices), "word_indices": indices}
        for role, indices in groups.items()
    ]
