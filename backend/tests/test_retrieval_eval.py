"""The evaluation must expose missing evidence and stale index predictions."""

from scripts.retrieval_eval import gate_failures, score_cases


def test_retrieval_evaluation_distinguishes_gold_coverage_from_ranking():
    chunks = [
        {"id": "right", "page_number": 4, "kind": "table_row", "text": "Revenue: 5 million"},
        {"id": "wrong", "page_number": 5, "kind": "prose", "text": "Revenue"},
    ]
    cases = [
        {
            "id": "found",
            "question": "What was revenue?",
            "page_number": 4,
            "kind": "table_row",
            "contains_all": ["5 million"],
        },
        {
            "id": "missing",
            "question": "What was profit?",
            "page_number": 4,
            "kind": "table_row",
            "contains_all": ["profit"],
        },
    ]
    report = score_cases(
        cases, chunks, {"found": ["stale", "wrong", "right"], "missing": ["wrong"]}, 2
    )
    assert report["gold_covered"] == 1
    assert report["hits_at_k"] == 0
    assert report["cases"][0]["first_relevant_rank"] == 3
    assert report["cases"][0]["unknown_prediction_count"] == 1
    assert report["cases"][1]["gold_chunk_count"] == 0


def test_quality_gate_rejects_stale_duplicate_and_low_rank_predictions():
    chunks = [{"id": "gold", "page_number": 1, "kind": "prose", "text": "Survey limitations"}]
    cases = [{"id": "q", "question": "Limitations?", "page_number": 1,
              "kind": "prose", "contains_all": ["limitations"]}]
    good = score_cases(cases, chunks, {"q": ["gold"]}, 1)
    assert gate_failures(good, 1.0, 1.0) == []
    bad = score_cases(cases, chunks, {"q": ["stale", "stale", "gold"]}, 1)
    failures = gate_failures(bad, 0.8, 0.5)
    assert len(failures) == 4
    assert any("duplicate" in item for item in failures)
    assert gate_failures(score_cases([], chunks, {}, 1), 0.8, 0.5)
