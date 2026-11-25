"""Audit real PDFs through the production extraction path, offline.

Usage (from the repository root, PDFs in a local folder; nothing is uploaded or stored):

    docker run --rm --network none -e PYTHONPATH=/srv \
      -v "$PWD/backend:/srv" -v "/path/to/pdfs:/pdfs:ro" \
      researchpilot-greenfield-backend:dev python scripts/real_pdf_coverage.py /pdfs

For each PDF it reports the extraction outcome, time, chunk count and the share of
readable body words that became searchable evidence, with withheld words grouped by
reason. Exit status is 1 if any PDF failed with layout_failure (a ResearchPilot bug).
"""

import hashlib
import json
import sys
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, cast

from app.modules.documents.chunks import make_chunks
from app.modules.documents.extraction import extract_with_layout
from app.modules.documents.quality import assess_page

EVIDENCE_ROLES = {"body", "abstract", "data_availability", "endnotes"}


def audit(path: Path) -> dict[str, Any]:
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    start = time.monotonic()
    pages, layouts, error = extract_with_layout(path, sha)
    seconds = round(time.monotonic() - start, 1)
    if error:
        return {"file": path.name, "error": error, "seconds": seconds}
    chunks = make_chunks(uuid.uuid4(), sha, layouts or [])
    chunked = {(c["page_number"], c["source_id"]) for c in chunks if c["kind"] == "prose"}
    body = kept = 0
    withheld: Counter[str] = Counter()
    for number, layout in enumerate(layouts or [], 1):
        quality = assess_page(layout)
        for passage in cast(list[dict[str, Any]], layout["passages"]):
            if passage.get("role", "body") not in EVIDENCE_ROLES:
                continue
            words = len(passage["text"].split())
            body += words
            if (number, passage["id"]) in chunked:
                kept += words
            elif quality["block_page"]:
                withheld["page_blocked"] += words
            elif quality["withhold_prose"]:
                withheld["page_prose_withheld"] += words
            elif passage["id"] in quality["blocked_passage_ids"]:
                withheld["passage_withheld"] += words
            else:
                withheld["other"] += words
    return {
        "file": path.name,
        "pages": len(pages or []),
        "seconds": seconds,
        "chunks": len(chunks),
        "body_words": body,
        "searchable_share": round(kept / body, 3) if body else None,
        "withheld_words": dict(withheld),
    }


def main() -> int:
    rows = [audit(path) for path in sorted(Path(sys.argv[1]).glob("*.pdf"))]
    for row in rows:
        print(json.dumps(row))
    scored = [r for r in rows if r.get("searchable_share") is not None]
    body = sum(r["body_words"] for r in scored)
    kept = sum(round(r["searchable_share"] * r["body_words"]) for r in scored)
    failures = Counter(str(r["error"]) for r in rows if "error" in r)
    print(json.dumps({"documents": len(rows), "failures": dict(failures),
                      "searchable_share": round(kept / body, 3) if body else None}))
    return 1 if failures.get("layout_failure") else 0


if __name__ == "__main__":
    raise SystemExit(main())
