"""Linux subprocess entrypoint. Never import this into the API or Celery process."""

import json
import logging
import os
import sys
import traceback

# Real figure-heavy papers spend most parsing time in pdfminer's vector-path
# decoding (LoRA, 26 pages: 22s). Keep CPU headroom below the wall timeout.
CPU_SECONDS = 90


def _diagnostic(error: BaseException) -> dict[str, str]:
    """Content-free location of an internal failure: no message, no source text."""
    frame = traceback.extract_tb(error.__traceback__)[-1]
    return {"type": type(error).__name__, "where": f"{os.path.basename(frame.filename)}:{frame.lineno}"}


def parse(path: str) -> dict[str, object]:
    try:
        from pypdf import PdfReader

        reader = PdfReader(path, strict=True)
        if reader.is_encrypted:
            return {"error": "encrypted_pdf"}
        if len(reader.pages) == 0 or len(reader.pages) > 300:
            return {"error": "page_limit"}
        pages: list[str] = []
        total = 0
        for page in reader.pages:
            # No HTML rendering, OCR, external URL fetching or embedded-file execution.
            text = (page.extract_text() or "").replace("\x00", "").strip()
            total += len(text)
            if len(text) > 100_000 or total > 2_000_000:
                raise MemoryError
            pages.append(text)
        if sum(len(p.strip()) for p in pages) < 40:
            return {"error": "insufficient_text"}
    except MemoryError:
        return {"error": "resource_limit"}
    except FileNotFoundError:
        return {"error": "storage_unavailable"}
    except Exception:
        return {"error": "invalid_pdf"}
    # pypdf accepted the file. Failures past this point are ResearchPilot layout
    # heuristics, not evidence that the user's PDF is invalid.
    try:
        import pdfplumber

        from app.modules.documents import reader as layout_reader

        with pdfplumber.open(path) as pdf:
            layouts = layout_reader.prepare_layouts(pdf)
    except MemoryError:
        return {"error": "resource_limit"}
    except Exception as error:
        return {"error": _blame(error), "diagnostic": _diagnostic(error)}
    return {"pages": pages, "layouts": layouts}


def _blame(error: BaseException) -> str:
    """invalid_pdf when the PDF libraries reject the file; layout_failure for our code."""
    from app.modules.documents.reader import InvalidPageBox

    if isinstance(error, InvalidPageBox):
        return "invalid_pdf"
    path = traceback.extract_tb(error.__traceback__)[-1].filename.replace("\\", "/")
    library = any(f"/{name}/" in path for name in ("pdfminer", "pdfplumber"))
    return "invalid_pdf" if library else "layout_failure"


def main() -> None:
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS + 5))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    logging.disable(logging.CRITICAL)
    print(json.dumps(parse(sys.argv[1]), ensure_ascii=True))


if __name__ == "__main__":
    main()
