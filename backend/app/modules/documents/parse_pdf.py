"""Linux subprocess entrypoint. Never import this into the API or Celery process."""

import json
import logging
import resource
import sys


def main() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (40, 45))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    logging.disable(logging.CRITICAL)
    result: dict[str, object]
    try:
        from pypdf import PdfReader

        reader = PdfReader(sys.argv[1], strict=True)
        if reader.is_encrypted:
            result = {"error": "encrypted_pdf"}
        elif len(reader.pages) == 0 or len(reader.pages) > 300:
            result = {"error": "page_limit"}
        else:
            pages: list[str] = []
            total = 0
            for page in reader.pages:
                # No HTML rendering, OCR, external URL fetching or embedded-file execution.
                text = (page.extract_text() or "").replace("\x00", "").strip()
                total += len(text)
                if len(text) > 100_000 or total > 2_000_000:
                    raise MemoryError
                pages.append(text)
            result = (
                {"pages": pages}
                if sum(len(p.strip()) for p in pages) >= 40
                else {"error": "insufficient_text"}
            )
    except MemoryError:
        result = {"error": "resource_limit"}
    except FileNotFoundError:
        result = {"error": "storage_unavailable"}
    except Exception:
        result = {"error": "invalid_pdf"}
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
