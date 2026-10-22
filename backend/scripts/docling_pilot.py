"""Offline, read-only Docling comparison for a supplied PDF.

Run with an isolated Docling interpreter; this is not an application dependency.
The original PDF is never modified and no application database is accessed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pages", nargs="*", type=int, default=[1, 8, 9, 18, 21, 22, 26, 27, 31])
    parser.add_argument("--page-range", nargs=2, type=int)
    args = parser.parse_args()

    options = PdfPipelineOptions()
    options.do_ocr = False
    options.do_table_structure = True
    options.do_picture_description = False
    options.do_chart_extraction = False
    options.generate_page_images = False
    options.generate_picture_images = False
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})

    started = time.perf_counter()
    conversion = {"page_range": tuple(args.page_range)} if args.page_range else {}
    result = converter.convert(str(args.pdf), **conversion)
    elapsed = time.perf_counter() - started
    doc = result.document
    selected_pages = set(args.pages)
    by_page: dict[int, list[dict[str, object]]] = defaultdict(list)
    labels: Counter[str] = Counter()
    hyperlink_items = 0
    no_provenance = 0
    for item, _level in doc.iterate_items():
        label = str(item.label)
        labels[label] += 1
        provenance = getattr(item, "prov", None) or []
        if not provenance:
            no_provenance += 1
        data = item.model_dump(mode="json", exclude_none=True)
        if any(value for value in _find_keys(data, "hyperlink")):
            hyperlink_items += 1
        for prov in provenance:
            page_no = int(prov.page_no)
            if page_no in selected_pages:
                by_page[page_no].append(
                    {
                        "label": label,
                        "text": str(getattr(item, "text", ""))[:600],
                        "bbox": prov.bbox.model_dump(mode="json"),
                        "hyperlinks": [str(value) for value in _find_keys(data, "hyperlink") if value],
                        "table_rows": getattr(getattr(item, "data", None), "num_rows", None),
                        "table_cols": getattr(getattr(item, "data", None), "num_cols", None),
                        "table_cells": data.get("data", {}).get("table_cells", []),
                    }
                )
    summary = {
        "source_sha256": hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
        "source_name": args.pdf.name,
        "conversion_status": str(result.status),
        "elapsed_seconds": round(elapsed, 2),
        "page_count": len(doc.pages),
        "page_range": args.page_range,
        "labels": dict(labels),
        "items_without_provenance": no_provenance,
        "items_with_hyperlinks": hyperlink_items,
        "selected_pages": dict(sorted(by_page.items())),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "selected_pages"}, indent=2))


def _find_keys(value: object, key: str):
    if isinstance(value, dict):
        for name, child in value.items():
            if name == key:
                yield child
            else:
                yield from _find_keys(child, key)
    elif isinstance(value, list):
        for child in value:
            yield from _find_keys(child, key)


if __name__ == "__main__":
    main()
