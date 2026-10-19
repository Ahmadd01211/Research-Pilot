import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from pypdf import __version__

EXTRACTOR_VERSION = "pypdf-" + __version__ + ":page-text-v1"
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


def extract(path: Path, expected_sha256: str) -> tuple[list[str] | None, str | None]:
    try:
        with path.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != expected_sha256:
                return None, "integrity_mismatch"
        process = subprocess.run(
            [sys.executable, "-m", "app.modules.documents.parse_pdf", str(path)],
            capture_output=True,
            timeout=60,
            check=False,
            env={"PATH": os.defpath, "LANG": "C.UTF-8"},
        )
        if process.returncode != 0 or len(process.stdout) > 12_500_000:
            return None, "resource_limit"
        result = json.loads(process.stdout)
        if "error" in result:
            return None, result["error"] if result["error"] in ERRORS else "invalid_pdf"
        pages = result.get("pages")
        if (
            not isinstance(pages, list)
            or not 1 <= len(pages) <= 300
            or any(not isinstance(p, str) or len(p) > 100_000 for p in pages)
            or sum(map(len, pages)) > 2_000_000
        ):
            return None, "invalid_pdf"
        return pages, None
    except subprocess.TimeoutExpired:
        return None, "parser_timeout"
    except OSError:
        return None, "storage_unavailable"
    except (ValueError, TypeError):
        return None, "invalid_pdf"
