"""Source-typed chunks, prepared locally without embeddings or image interpretation."""

import hashlib
import json
import re
from typing import Any
from uuid import UUID

from app.modules.documents.quality import assess_page

CHUNKER_VERSION = "source-types-v8"


def make_chunks(
    document_id: UUID, source_hash: str, layouts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    chunks = []
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
            if passage.get("role", "body") not in {"body", "abstract"}:
                continue
            # Undecodable mathematical font glyphs must not become answer evidence.
            if any(0xE000 <= ord(c) <= 0xF8FF for c in passage["text"]):
                continue
            entries.append(
                (
                    "prose",
                    passage["id"],
                    passage["text"],
                    {"passage_id": passage["id"], "evidence_role": passage.get("role", "body")},
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
            labelled = detection.startswith("numbered-model-") or detection in {
                "aligned-labelled-columns",
                "aligned-numbered-section-columns",
            }
            section = ""
            subsection = ""
            for row_number, row in enumerate(table["rows"], 1):
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
