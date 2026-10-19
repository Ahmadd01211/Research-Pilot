"""Passive PDF links: retain annotations/visible destinations; never fetch or execute."""

import hashlib
import json
import re
from typing import Any
from urllib.parse import urlsplit

from pdfminer.pdfdocument import PDFDestinationNotFound
from pdfminer.pdftypes import PDFObjRef, resolve1


def safe_target(value: Any) -> str | None:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 2048
        or any(ord(c) < 33 or ord(c) == 127 for c in value)
        or "\\" in value
    ):
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme.lower() in {"http", "https"}
            and parsed.hostname
            and not parsed.username
            and not parsed.password
        ):
            _ = parsed.port
            return value
        if (
            parsed.scheme.lower() == "mailto"
            and re.fullmatch(r"[^@\s/?]+@[^@\s/?]+", parsed.path)
            and not parsed.query
            and not parsed.fragment
        ):
            return value
    except ValueError:
        pass
    return None


def page_links(
    view: Any, words: list[dict[str, Any]], page_ids: dict[int, int], page_count: int
) -> list[dict[str, Any]]:
    x, y, right, bottom = view.bbox
    width, height = right - x, bottom - y
    root = getattr(view, "root_page", view)
    annotations = getattr(root, "annots", []) or []
    if len(annotations) > 500:
        raise MemoryError
    links: list[dict[str, Any]] = []

    def add(
        box: list[float], target: str | None, target_page: int | None, status: str, origin: str
    ) -> None:
        if not 0 <= box[0] < box[2] <= 1 or not 0 <= box[1] < box[3] <= 1:
            return
        indices = [
            i
            for i, w in enumerate(words)
            if box[0] <= (w["box"][0] + w["box"][2]) / 2 <= box[2]
            and box[1] <= (w["box"][1] + w["box"][3]) / 2 <= box[3]
        ]
        links.append(
            {
                "box": box,
                "text": " ".join(words[i]["text"] for i in indices),
                "word_indices": indices,
                "target": target,
                "target_page": target_page,
                "status": status,
                "origin": origin,
                "source_ids": [],
            }
        )

    for annotation in annotations:
        data = annotation.get("data", {})
        if not isinstance(data, dict):
            continue
        if getattr(data.get("Subtype"), "name", None) != "Link":
            continue
        try:
            box = [
                max(0.0, min(1.0, v))
                for v in [
                    (annotation["x0"] - x) / width,
                    (annotation["top"] - y) / height,
                    (annotation["x1"] - x) / width,
                    (annotation["bottom"] - y) / height,
                ]
            ]
            action = resolve1(data.get("A", {}))
            action = action if isinstance(action, dict) else {}
            action_name = getattr(action.get("S"), "name", None)
            if action_name not in {None, "URI", "GoTo"}:
                add(box, None, None, "blocked", "annotation")
                continue
            uri = annotation.get("uri")
            if uri:
                target = safe_target(uri)
                add(box, target, None, "allowed" if target else "blocked", "annotation")
                continue
            dest = action.get("D", data.get("Dest"))
            if dest is not None:
                if isinstance(dest, (bytes, str)):
                    try:
                        dest = view.pdf.doc.get_dest(dest)
                    except (KeyError, ValueError, TypeError, PDFDestinationNotFound):
                        dest = None
                dest = resolve1(dest)
                if isinstance(dest, dict):
                    dest = resolve1(dest.get("D"))
                destination = None
                if isinstance(dest, (list, tuple)) and dest:
                    ref = dest[0]
                    if isinstance(ref, PDFObjRef):
                        destination = page_ids.get(ref.objid)
                    elif (
                        isinstance(ref, int) and not isinstance(ref, bool) and 0 <= ref < page_count
                    ):
                        destination = ref + 1
                add(
                    box,
                    None,
                    destination,
                    "internal" if destination else "unresolved",
                    "annotation",
                )
            else:
                add(box, None, None, "blocked", "annotation")
        except (KeyError, ValueError, TypeError, AttributeError):
            # A malformed action cannot break otherwise readable evidence or run code.
            continue
    for i, word in enumerate(words):
        value = word["text"].rstrip(".,;")
        while value.endswith(")") and value.count(")") > value.count("("):
            value = value[:-1]
        if re.match(r"^https?://", value, re.IGNORECASE):
            target = safe_target(value)
            origin = "visible_url"
        elif re.fullmatch(r"10\.\d{4,9}/[^\s]+", value):
            target = safe_target("https://doi.org/" + value)
            origin = "visible_doi"
        else:
            continue
        if target and not any(
            link["target"] == target and i in link["word_indices"] for link in links
        ):
            add(word["box"], target, None, "allowed", origin)
    if len(links) > 500:
        raise MemoryError
    return links


def finalize_links(layout: dict[str, Any], page_number: int) -> None:
    anchors = [(p["id"], set(p["word_indices"])) for p in layout["passages"]]
    anchors += [
        (c["id"], set(c["word_indices"]))
        for t in layout["tables"]
        for row in t["rows"]
        for c in row
    ]
    anchors += [(f["id"], set(f["caption_word_indices"])) for f in layout["figures"]]
    for link in layout.get("links", []):
        indices = set(link["word_indices"])
        link["source_ids"] = [identity for identity, words in anchors if indices & words]
        link["id"] = hashlib.sha256(
            json.dumps(
                [layout["version"], page_number, link],
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode()
        ).hexdigest()
