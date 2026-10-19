import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from pdfplumber import __version__ as layout_version
from pypdf import __version__

from app.modules.documents.schemas import ReaderLayout

EXTRACTOR_VERSION = (
    "pypdf-" + __version__ + ":page-text-v1+pdfplumber-" + layout_version + ":word-passages-v1"
)
ERRORS = {
    "encrypted_pdf",
    "page_limit",
    "insufficient_text",
    "resource_limit",
    "storage_unavailable",
    "invalid_pdf",
    "integrity_mismatch",
    "parser_timeout",
    "worker_failure",
}
TRANSIENT = {"storage_unavailable", "worker_failure"}


def extract_with_layout(
    path: Path, expected_sha256: str
) -> tuple[list[str] | None, list[dict[str, object]] | None, str | None]:
    try:
        with path.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != expected_sha256:
                return None, None, "integrity_mismatch"
        process = subprocess.run(
            [sys.executable, "-m", "app.modules.documents.parse_pdf", str(path)],
            capture_output=True,
            timeout=60,
            check=False,
            env={"PATH": os.defpath, "LANG": "C.UTF-8"},
        )
        if process.returncode != 0 or len(process.stdout) > 64_000_000:
            return None, None, "resource_limit"
        result = json.loads(process.stdout)
        if "error" in result:
            return None, None, result["error"] if result["error"] in ERRORS else "invalid_pdf"
        pages = result.get("pages")
        if (
            not isinstance(pages, list)
            or not 1 <= len(pages) <= 300
            or any(not isinstance(p, str) or len(p) > 100_000 for p in pages)
            or sum(map(len, pages)) > 2_000_000
        ):
            return None, None, "invalid_pdf"
        layouts = result.get("layouts")
        if not isinstance(layouts, list) or len(layouts) != len(pages):
            return None, None, "invalid_pdf"
        checked = [ReaderLayout.model_validate(layout) for layout in layouts]
        for layout in checked:
            if len(layout.words) > 12000 or layout.width <= 0 or layout.height <= 0:
                return None, None, "resource_limit"
            for word in layout.words:
                a, b, c, d = word.box
                if not 0 <= a < c <= 1 or not 0 <= b < d <= 1:
                    return None, None, "invalid_pdf"
            for passage in layout.passages + [
                cell for table in layout.tables for row in table.rows for cell in row
            ]:
                if any(not 0 <= i < len(layout.words) for i in passage.word_indices):
                    return None, None, "invalid_pdf"
        return pages, [layout.model_dump(mode="json") for layout in checked], None
    except subprocess.TimeoutExpired:
        return None, None, "parser_timeout"
    except OSError:
        return None, None, "storage_unavailable"
    except (ValueError, TypeError):
        return None, None, "invalid_pdf"


def extract(path: Path, expected_sha256: str) -> tuple[list[str] | None, str | None]:
    pages, _, error = extract_with_layout(path, expected_sha256)
    return pages, error
