"""Routing policy for the native parser and an optional Docling fallback.

This module deliberately does not import Docling. The normal API/worker image
stays small; a separate worker can consume the candidate page list later.
Pages that need fallback remain withheld from retrieval until that worker
publishes output that passes the same source-anchor checks.
"""

from typing import Any  # noqa: I001

HYBRID_VERSION = "hybrid-router-v3"


def route_page(quality: dict[str, Any]) -> dict[str, Any]:
    findings = quality.get("findings", [])
    codes = {str(item.get("code")) for item in findings}
    if quality.get("block_page") or "no_measured_text" in codes:
        reason = "native extraction has no trustworthy measured text"
    elif codes & {
        "unstructured_table",
        "uncertain_table",
        "fragmented_text",
        "uncertain_figure_boundary",
        "invalid_figure_anchor",
        "oversized_figure_region",
        "misaligned_figure_caption",
        "caption_crosses_columns",
        "dense_numeric_prose",
        "undecoded_font_glyphs",
    }:
        reason = "native layout quality needs a structured fallback"
    else:
        return {
            "version": HYBRID_VERSION,
            "route": "native",
            "status": "trusted",
            "reason": None,
        }
    return {
        "version": HYBRID_VERSION,
        "route": "docling",
        "status": "candidate",
        "reason": reason,
    }
