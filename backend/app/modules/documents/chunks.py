"""Source-typed chunks, prepared locally without embeddings or image interpretation."""

import hashlib
import json
from typing import Any
from uuid import UUID

CHUNKER_VERSION = "source-types-v3"


def make_chunks(
    document_id: UUID, source_hash: str, layouts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    chunks = []
    for number, layout in enumerate(layouts, 1):
        entries = []
        uncertain = any(f["box"] is None for f in layout.get("figures", []))
        for passage in [] if uncertain else layout["passages"]:
            # Undecodable mathematical font glyphs must not become answer evidence.
            if any(0xE000 <= ord(c) <= 0xF8FF for c in passage["text"]):
                continue
            entries.append(("prose", passage["id"], passage["text"], {"passage_id": passage["id"]}))
        for table in layout.get("tables", []):
            for row_number, row in enumerate(table["rows"], 1):
                text = " | ".join(cell["text"] for cell in row)
                if table.get("detection") == "numbered-model-columns" and row_number > 1:
                    text = " | ".join(
                        f"{header['text']}: {cell['text'] or '[blank in source]'}"
                        for header, cell in zip(table["rows"][0], row, strict=True)
                    )
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
