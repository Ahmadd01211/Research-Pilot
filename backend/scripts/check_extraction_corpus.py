"""Run with python -m scripts.check_extraction_corpus; exits nonzero on any regression."""

import json

from tests.pdf_corpus import CASES
from tests.test_pdf_corpus import check_case


def main():
    results = []
    failed = False
    for case in CASES:
        try:
            results.append({"status": "passed", **check_case(case)})
        except Exception as exc:
            failed = True
            results.append({"case": case, "status": "failed", "error": type(exc).__name__})
    print(
        json.dumps(
            {
                "scope": "synthetic regression coverage, not universal PDF accuracy",
                "cases": results,
            },
            indent=2,
        )
    )
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
