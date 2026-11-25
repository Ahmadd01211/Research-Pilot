import hashlib
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from pdfplumber import __version__ as layout_version
from pydantic import ValidationError
from pypdf import __version__

from app.modules.documents.links import safe_target
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
    "layout_failure",
}
TRANSIENT = {"storage_unavailable", "worker_failure"}
# Not retried automatically (deterministic), but our heuristics change between
# releases, so the owner may request another bounded attempt.
USER_RETRYABLE = TRANSIENT | {"layout_failure"}
PARSER_WALL_SECONDS = 100  # Above the parser CPU cap, below Celery's soft limit.
log = logging.getLogger(__name__)
Result = tuple[list[str] | None, list[dict[str, object]] | None, str | None]


class LayoutContractError(ValueError):
    """Reader output broke its own contract: a ResearchPilot bug, not a bad PDF."""


def _box(value: tuple[float, float, float, float], what: str) -> None:
    a, b, c, d = value
    if not 0 <= a < c <= 1 or not 0 <= b < d <= 1:
        raise LayoutContractError(what)


def _check_layouts(raw: list[Any], page_count: int) -> list[ReaderLayout]:
    checked = []
    for number, layout_data in enumerate(raw, 1):
        try:
            layout = ReaderLayout.model_validate(layout_data)
        except ValidationError as error:
            fields = sorted({".".join(map(str, e["loc"])) for e in error.errors()})[:5]
            raise LayoutContractError(f"page {number} schema: {', '.join(fields)}") from None
        words = len(layout.words)
        if layout.width <= 0 or layout.height <= 0:
            raise LayoutContractError(f"page {number} size")
        if words > 12000:
            raise MemoryError
        for word in layout.words:
            _box(word.box, f"page {number} word box")
        if len(layout.links) > 500:
            raise MemoryError
        for link in layout.links:
            _box(link.box, f"page {number} link box")
            if any(not 0 <= i < words for i in link.word_indices):
                raise LayoutContractError(f"page {number} link anchor")
            if link.status == "allowed" and (
                link.target is None or safe_target(link.target) != link.target
            ):
                raise LayoutContractError(f"page {number} link target")
            if link.status == "internal" and (
                link.target_page is None or not 1 <= link.target_page <= page_count
            ):
                raise LayoutContractError(f"page {number} internal link")
        for figure in layout.figures:
            if figure.box:
                _box(figure.box, f"page {number} figure box")
            if any(not 0 <= i < words for i in figure.caption_word_indices):
                raise LayoutContractError(f"page {number} figure anchor")
        for passage in layout.passages + [
            cell for table in layout.tables for row in table.rows for cell in row
        ]:
            if any(not 0 <= i < words for i in passage.word_indices):
                raise LayoutContractError(f"page {number} passage anchor")
        checked.append(layout)
    return checked


def checked_result(result: dict[str, Any], document: str = "unknown") -> Result:
    """Validate parser subprocess output; distinguish bad PDFs from our own bugs.

    ``document`` is the stored original's UUID file name, never the user's filename.
    """
    if "error" in result:
        error = result["error"] if result["error"] in ERRORS else "invalid_pdf"
        if result.get("diagnostic"):
            log.error("PDF parse %s document=%s at %s", error, document, result["diagnostic"])
        return None, None, error
    pages = result.get("pages")
    if (
        not isinstance(pages, list)
        or not 1 <= len(pages) <= 300
        or any(not isinstance(p, str) or len(p) > 100_000 for p in pages)
        or sum(map(len, pages)) > 2_000_000
    ):
        return None, None, "invalid_pdf"
    layouts = result.get("layouts")
    try:
        if not isinstance(layouts, list) or len(layouts) != len(pages):
            raise LayoutContractError("layout count")
        checked = _check_layouts(layouts, len(pages))
    except MemoryError:
        return None, None, "resource_limit"
    except LayoutContractError as error:
        log.error("PDF layout contract violated document=%s: %s", document, error)
        return None, None, "layout_failure"
    return pages, [layout.model_dump(mode="json") for layout in checked], None


def extract_with_layout(path: Path, expected_sha256: str) -> Result:
    try:
        with path.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != expected_sha256:
                return None, None, "integrity_mismatch"
        process = subprocess.run(
            [sys.executable, "-m", "app.modules.documents.parse_pdf", str(path)],
            capture_output=True,
            timeout=PARSER_WALL_SECONDS,
            check=False,
            env={"PATH": os.defpath, "LANG": "C.UTF-8"},
        )
        if process.returncode != 0 or len(process.stdout) > 64_000_000:
            return None, None, "resource_limit"
        return checked_result(json.loads(process.stdout), path.name)
    except subprocess.TimeoutExpired:
        return None, None, "parser_timeout"
    except OSError:
        return None, None, "storage_unavailable"
    except (ValueError, TypeError):
        return None, None, "invalid_pdf"


def extract(path: Path, expected_sha256: str) -> tuple[list[str] | None, str | None]:
    pages, _, error = extract_with_layout(path, expected_sha256)
    return pages, error
