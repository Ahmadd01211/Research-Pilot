from uuid import uuid4

from app.modules.documents.search import SearchHit, distinct_evidence


def test_repeated_prose_is_replaced_with_next_distinct_evidence():
    document = uuid4()
    text = "The survey examines adoption across firms and countries using comparable worker evidence. " * 8

    def hit(identity: str, value: str, **changes: object) -> SearchHit:
        return SearchHit.model_validate({
            "chunk_id": identity, "document_id": document, "source_sha256": "a" * 64,
            "reader_version": "current", "page_number": 1, "kind": "prose",
            "source_id": identity, "text": value, "source_metadata": {}, "distance": 0.2,
            **changes,
        })

    candidates = [hit("first", text), hit("repeat", text + " Further discussion."),
                  hit("finding", "Management practices explain some remaining differences.")]
    assert [item.chunk_id for item in distinct_evidence(candidates, 2)] == ["first", "finding"]
    # Independent sources and changed numerical findings retain their evidence.
    candidates = [hit("first", text + " 12.5%"), hit("changed", text + " 15.2%"),
                  hit("other", text + " 12.5%", document_id=uuid4()),
                  hit("row1", text, kind="table_row"), hit("row2", text, kind="table_row")]
    assert len(distinct_evidence(candidates, 8)) == 5
