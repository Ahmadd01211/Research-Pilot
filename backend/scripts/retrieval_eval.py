"""Offline retrieval evaluation over the same source chunks prepared for indexing.

Run from backend/: python -m scripts.retrieval_eval --pdf PAPER.pdf --cases CASES.json
No document is uploaded and no embedding provider is contacted. A predictions JSON
mapping case IDs to ranked chunk IDs can replace the lexical baseline later.
"""

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any
from uuid import UUID

import pdfplumber

from app.modules.documents.chunks import CHUNKER_VERSION, make_chunks
from app.modules.documents.reader import READER_VERSION, prepare_layouts


def tokens(value: str) -> list[str]:
    return re.findall(r"\w+", value.casefold())


def lexical_ranking(question: str, chunks: list[dict[str, Any]]) -> list[str]:
    """Small, deterministic BM25 baseline; it is not the planned vector search."""
    query = set(tokens(question))
    if not query or not chunks:
        return []
    documents = [Counter(tokens(chunk["text"])) for chunk in chunks]
    lengths = [sum(counts.values()) for counts in documents]
    average = sum(lengths) / max(len(lengths), 1)
    frequency = Counter(term for counts in documents for term in query if term in counts)
    scores = []
    for chunk, counts, length in zip(chunks, documents, lengths, strict=True):
        score = 0.0
        for term in query:
            count = counts[term]
            if not count:
                continue
            idf = math.log(1 + (len(chunks) - frequency[term] + 0.5) / (frequency[term] + 0.5))
            score += idf * count * 2.2 / (count + 1.2 * (0.25 + 0.75 * length / average))
        scores.append((score, chunk["id"]))
    return [identity for score, identity in sorted(scores, key=lambda item: (-item[0], item[1])) if score]


def gold_ids(case: dict[str, Any], chunks: list[dict[str, Any]]) -> set[str]:
    phrases = [phrase.casefold() for phrase in case["contains_all"]]
    return {
        chunk["id"]
        for chunk in chunks
        if chunk["page_number"] == case["page_number"]
        and chunk["kind"] == case["kind"]
        and all(phrase in chunk["text"].casefold() for phrase in phrases)
    }


def score_cases(
    cases: list[dict[str, Any]], chunks: list[dict[str, Any]], predictions: dict[str, list[str]] | None,
    top_k: int,
) -> dict[str, Any]:
    known = {chunk["id"]: chunk for chunk in chunks}
    results = []
    reciprocal_ranks = []
    for case in cases:
        gold = gold_ids(case, chunks)
        ranking = (
            predictions.get(case["id"], [])
            if predictions is not None
            else lexical_ranking(case["question"], chunks)
        )
        # Unknown IDs must be visible: a stale embedding index is not a valid hit.
        unknown = [identity for identity in ranking if identity not in known]
        duplicates = len(ranking) - len(set(ranking))
        rank = next((index for index, identity in enumerate(ranking, 1) if identity in gold), None)
        hit = rank is not None and rank <= top_k
        reciprocal_ranks.append(1 / rank if rank is not None else 0)
        results.append(
            {
                "id": case["id"],
                "question": case["question"],
                "expected_page": case["page_number"],
                "expected_kind": case["kind"],
                "gold_chunk_count": len(gold),
                "first_relevant_rank": rank,
                "hit_at_k": hit,
                "unknown_prediction_count": len(unknown),
                "duplicate_prediction_count": duplicates,
                "top_k": [
                    {
                        "chunk_id": identity,
                        "page_number": known[identity]["page_number"] if identity in known else None,
                        "kind": known[identity]["kind"] if identity in known else None,
                        "relevant": identity in gold,
                    }
                    for identity in ranking[:top_k]
                ],
            }
        )
    total = len(results)
    return {
        "questions": total,
        "gold_covered": sum(item["gold_chunk_count"] > 0 for item in results),
        "hits_at_k": sum(item["hit_at_k"] for item in results),
        "recall_at_k": sum(item["hit_at_k"] for item in results) / total if total else 0,
        "mean_reciprocal_rank": sum(reciprocal_ranks) / total if total else 0,
        "cases": results,
    }


def gate_failures(report: dict[str, Any], minimum_recall: float, minimum_mrr: float) -> list[str]:
    """Fail closed on incomplete evidence or invalid predictions before checking rank quality."""
    failures = []
    if not report["questions"]:
        failures.append("No evaluation questions")
    if report["gold_covered"] != report["questions"]:
        failures.append("Expected evidence is missing from eligible chunks")
    if any(item["unknown_prediction_count"] for item in report["cases"]):
        failures.append("Predictions contain unknown or stale chunk IDs")
    if any(item["duplicate_prediction_count"] for item in report["cases"]):
        failures.append("Predictions contain duplicate chunk IDs")
    if report["recall_at_k"] < minimum_recall:
        failures.append("Recall at k is below the configured threshold")
    if report["mean_reciprocal_rank"] < minimum_mrr:
        failures.append("Mean reciprocal rank is below the configured threshold")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--document-id", type=UUID, default=UUID(int=1))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--minimum-recall", type=float, default=0.8)
    parser.add_argument("--minimum-mrr", type=float, default=0.5)
    args = parser.parse_args()
    if args.top_k < 1 or args.top_k > 50:
        parser.error("--top-k must be between 1 and 50")
    if not 0 <= args.minimum_recall <= 1 or not 0 <= args.minimum_mrr <= 1:
        parser.error("Quality thresholds must be between 0 and 1")
    manifest = json.loads(args.cases.read_text(encoding="utf-8"))
    cases = manifest["cases"]
    if not cases or len({case["id"] for case in cases}) != len(cases):
        parser.error("Cases must have unique IDs")
    source_hash = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    if source_hash != manifest["source_sha256"]:
        parser.error("PDF checksum does not match the reviewed evaluation source")
    with pdfplumber.open(args.pdf) as pdf:
        layouts = prepare_layouts(pdf)
    chunks = make_chunks(args.document_id, source_hash, layouts)
    predictions = json.loads(args.predictions.read_text(encoding="utf-8")) if args.predictions else None
    report = score_cases(cases, chunks, predictions, args.top_k)
    report.update(
        {
            "source_sha256": source_hash,
            "document_id": str(args.document_id),
            "reader_version": READER_VERSION,
            "chunker_version": CHUNKER_VERSION,
            "retrieval": "provided_predictions" if predictions is not None else "local_bm25_baseline",
            "eligible_chunks": len(chunks),
            "top_k_value": args.top_k,
        }
    )
    failures = gate_failures(report, args.minimum_recall, args.minimum_mrr)
    report["quality_gate"] = {"passed": not failures, "failures": failures,
                              "minimum_recall": args.minimum_recall,
                              "minimum_mrr": args.minimum_mrr}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
