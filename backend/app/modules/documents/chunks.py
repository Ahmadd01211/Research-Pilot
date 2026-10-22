"""Source-typed chunks, prepared locally without embeddings or image interpretation."""

import hashlib
import json
import re
from typing import Any
from uuid import UUID

from app.modules.documents.quality import assess_page

CHUNKER_VERSION = "source-types-v12"


def nearby_table_caption(layout: dict[str, Any], table: dict[str, Any]) -> dict[str, Any] | None:
    """Attach a measured caption only when its association is unambiguous."""
    words = layout.get("words", [])
    box = table.get("box")
    if not words or not box:
        return None
    candidates = []
    for passage in layout.get("passages", []):
        if not re.match(r"^TABLE\s+[A-Za-z]?\d+[a-z]?\b", passage["text"], re.I):
            continue
        indices = passage.get("word_indices", [])
        if not indices or len(passage["text"]) > 240:
            continue
        left = min(words[i]["box"][0] for i in indices)
        top = min(words[i]["box"][1] for i in indices)
        right = max(words[i]["box"][2] for i in indices)
        bottom = max(words[i]["box"][3] for i in indices)
        if (
            min(right, box[2]) <= max(left, box[0])
            or top > box[1] + 0.06
            or bottom > box[3]
            or max(0.0, box[1] - bottom) > 0.08
        ):
            continue
        candidates.append(passage)
    return candidates[0] if len(candidates) == 1 else None


def make_chunks(
    document_id: UUID, source_hash: str, layouts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    chunks = []
    last_endnote: int | None = None
    last_endnote_page = 0
    for number, layout in enumerate(layouts, 1):
        entries = []
        quality = assess_page(layout) if "words" in layout else None
        if quality and quality["block_page"]:
            continue
        uncertain = any(f["box"] is None for f in layout.get("figures", [])) or bool(
            quality and quality["withhold_prose"]
        )
        for passage in [] if uncertain else layout["passages"]:
            if quality and passage["id"] in quality["blocked_passage_ids"]:
                continue
            role = passage.get("role", "body")
            if role not in {"body", "abstract", "data_availability", "endnotes"}:
                continue
            if role == "endnotes" and passage["text"].strip().upper() == "ENDNOTES":
                continue
            # Undecodable mathematical font glyphs must not become answer evidence.
            if any(0xE000 <= ord(c) <= 0xF8FF for c in passage["text"]):
                continue
            search_text = passage["text"]
            source_metadata: dict[str, Any] = {"passage_id": passage["id"], "evidence_role": role}
            if role == "endnotes":
                marker = re.match(r"^([1-9]\d{0,2})\s", search_text)
                if marker:
                    last_endnote = int(marker.group(1))
                    last_endnote_page = number
                elif last_endnote is not None and number - last_endnote_page <= 1:
                    search_text = f"Endnote {last_endnote} (continued): {search_text}"
                if last_endnote is not None:
                    source_metadata["endnote_number"] = last_endnote
            entries.append(
                (
                    "prose",
                    passage["id"],
                    search_text,
                    source_metadata,
                )
            )
        for table_index, table in enumerate(layout.get("tables", [])):
            if quality and table_index in quality["blocked_table_indices"]:
                continue
            if table.get("detection", "").endswith("ambiguous"):
                continue
            # Layout adapters share one chunk contract. A new adapter must not
            # silently fall back to unlabelled numeric rows.
            detection = table.get("detection", "")
            caption = nearby_table_caption(layout, table)
            labelled = detection.startswith("numbered-model-") or detection in {
                "aligned-labelled-columns",
                "aligned-numbered-section-columns",
                "continued-numbered-columns",
                "regression-model-columns",
            }
            section = ""
            subsection = ""
            for row_number, row in enumerate(table["rows"], 1):
                # Column labels describe subsequent evidence; embedding them as
                # a standalone header chunk adds noise without any observation.
                if labelled and row_number == 1:
                    continue
                if (
                    labelled
                    and row_number > 1
                    and row[0]["text"]
                    and not any(c["text"] for c in row[1:])
                ):
                    if re.match(r"^[A-Z]\.", row[0]["text"]):
                        section = row[0]["text"]
                        subsection = ""
                    else:
                        subsection = row[0]["text"]
                    continue
                text = " | ".join(cell["text"] for cell in row)
                if labelled and row_number > 1:
                    text = " | ".join(
                        f"{header['text']}: {cell['text'] or '[blank in source]'}"
                        if header["text"]
                        else cell["text"]
                        for header, cell in zip(table["rows"][0], row, strict=True)
                    )
                if section or subsection:
                    text = " | ".join(value for value in [section, subsection, text] if value)
                if caption:
                    text = caption["text"] + " | " + text
                source_id = hashlib.sha256(
                    "|".join(cell["id"] for cell in row).encode()
                ).hexdigest()
                entries.append(
                    (
                        "table_row",
                        source_id,
                        text,
                        {
                            "row_number": row_number,
                            "cell_ids": [cell["id"] for cell in row],
                            "box": table["box"],
                            "table_caption_id": caption["id"] if caption else None,
                        },
                    )
                )
        for figure in layout.get("figures", []):
            if figure["caption"]:
                entries.append(
                    (
                        "figure_caption",
                        figure["id"],
                        figure["caption"],
                        {
                            "figure_id": figure["id"],
                            "label": figure["label"],
                            "image_interpretation": False,
                        },
                    )
                )
        for kind, source_id, text, metadata in entries:
            if not text.strip():
                continue
            anchors = {source_id, *metadata.get("cell_ids", [])}
            if metadata.get("table_caption_id"):
                anchors.add(metadata["table_caption_id"])
            metadata["links"] = [
                {
                    "id": link["id"],
                    "target": link["target"],
                    "target_page": link["target_page"],
                    "origin": link["origin"],
                }
                for link in layout.get("links", [])
                if link["status"] in {"allowed", "internal"}
                and anchors.intersection(link["source_ids"])
            ]
            metadata["quality_version"] = quality["version"] if quality else "legacy-unassessed"
            identity = [
                str(document_id),
                source_hash,
                layout["version"],
                CHUNKER_VERSION,
                number,
                kind,
                source_id,
                text,
                metadata,
            ]
            key = hashlib.sha256(
                json.dumps(
                    identity, sort_keys=True, separators=(",", ":"), ensure_ascii=True
                ).encode()
            ).hexdigest()
            chunks.append(
                {
                    "id": key,
                    "document_id": document_id,
                    "source_sha256": source_hash,
                    "reader_version": layout["version"],
                    "chunker_version": CHUNKER_VERSION,
                    "page_number": number,
                    "kind": kind,
                    "source_id": source_id,
                    "text": text,
                    "source_metadata": metadata,
                }
            )
    return chunks
