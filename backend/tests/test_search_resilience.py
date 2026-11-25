"""Search stays honest when some papers are still indexing or the embedder is down."""

import threading
import time
from uuid import UUID

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from app.core.config import Settings
from app.embedder.server import PriorityGate, slices
from app.modules.documents import indexing, search
from app.modules.documents.chunks import CHUNKER_VERSION
from app.modules.documents.embeddings import EmbeddingFailure
from app.modules.documents.models import Document, DocumentPageText, EvidenceChunk
from app.modules.documents.reader import READER_VERSION
from tests.test_documents import PDF, upload
from tests.test_embeddings import _owner_id
from tests.test_projects import authenticated, create

SETTINGS = Settings(embedding_enabled=True, google_api_key=SecretStr("synthetic-secret"))
VECTOR = [1.0] + [0.0] * 767


class Provider:
    """Embeds everything to the same vector; question() may be told to fail."""

    failure: EmbeddingFailure | None = None

    def __init__(self, _settings):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass

    def documents(self, texts):
        return [VECTOR for _ in texts]

    def question(self, _question):
        if Provider.failure:
            raise Provider.failure
        return VECTOR


@pytest.fixture
def papers(client, monkeypatch):
    """Two extracted papers; only the first is indexed."""
    Provider.failure = None
    monkeypatch.setattr(indexing, "provider_for", Provider)
    monkeypatch.setattr(search, "provider_for", Provider)
    authenticated(client)
    project_id = UUID(create(client)["id"])
    ids = [UUID(upload(client, str(project_id), PDF + suffix, f"paper{n}.pdf").json()["document"]["id"])
           for n, suffix in enumerate([b"", b"\n%second"])]
    factory = client.app.state.session_factory
    with factory() as db:
        for number, document_id in enumerate(ids):
            paper = db.get(Document, document_id)
            assert paper is not None and paper.processing is not None
            paper.processing.state = "extracted"
            db.add(DocumentPageText(document_id=document_id, page_number=1, text="Text.",
                                    layout={"version": READER_VERSION}))
            db.add(EvidenceChunk(
                id=f"chunk-{number}", document_id=document_id, source_sha256=paper.sha256,
                reader_version=READER_VERSION, chunker_version=CHUNKER_VERSION, page_number=1,
                kind="prose", source_id=f"passage-{number}",
                text=f"Firm adoption was measured in survey {number}.", source_metadata={},
            ))
        db.commit()
        owner = _owner_id(db, project_id)
        ready = indexing.queue_index(db, owner, project_id, ids[0], SETTINGS)
        indexing.queue_index(db, owner, project_id, ids[1], SETTINGS)  # stays queued
        assert ready is not None
        ready_id = ready.id
    indexing.run_index(factory, SETTINGS, ready_id)
    return factory, owner, project_id, ids


def run(papers, document_ids):
    factory, owner, project_id, _ = papers
    with factory() as db:
        return search.search(db, owner, project_id, search.SearchRequest(
            question="How was firm adoption measured?", document_ids=document_ids,
        ), SETTINGS)


def test_ready_papers_are_searched_and_indexing_ones_are_named(papers):
    ready, indexing_paper = papers[3]
    result = run(papers, [ready, indexing_paper])
    assert result.retrieval == "hybrid"
    assert {hit.document_id for hit in result.hits} == {ready}
    assert [(s.document_id, s.reason) for s in result.skipped_documents] == [
        (indexing_paper, "indexing")
    ]


def test_no_ready_paper_is_refused_with_a_reason(papers):
    with pytest.raises(HTTPException) as error:
        run(papers, [papers[3][1]])
    assert error.value.status_code == 409
    assert "indexing" in error.value.detail


def test_embedder_outage_falls_back_to_labelled_keyword_search(papers):
    Provider.failure = EmbeddingFailure("provider_unavailable", True)
    ready, indexing_paper = papers[3]
    result = run(papers, [ready, indexing_paper])
    assert result.retrieval == "keyword_fallback"
    assert result.model == search.KEYWORD_MODEL
    assert {hit.document_id for hit in result.hits} == {ready}
    assert [s.reason for s in result.skipped_documents] == ["indexing"]


def test_a_broken_embedder_response_is_an_error_not_a_fallback(papers):
    Provider.failure = EmbeddingFailure("provider_shape", False)
    with pytest.raises(HTTPException) as error:
        run(papers, [papers[3][0]])
    assert error.value.status_code == 502


def test_document_batches_are_sliced_so_questions_wait_seconds_not_minutes():
    assert slices(["a" * 900] * 8) == [["a" * 900] * 2] * 4
    assert slices(["x" * 8000, "short"]) == [["x" * 8000], ["short"]]
    assert slices(["one"]) == [["one"]]


def test_waiting_questions_run_before_waiting_document_slices():
    gate = PriorityGate()
    order: list[str] = []
    gate_held = threading.Event()

    def worker(name: str, query: bool) -> None:
        with gate.hold(query):
            order.append(name)

    with gate.hold(query=False):  # a document slice is running
        gate_held.set()
        document = threading.Thread(target=worker, args=("document", False))
        document.start()
        time.sleep(0.05)
        question = threading.Thread(target=worker, args=("question", True))
        question.start()
        time.sleep(0.05)
    document.join(2)
    question.join(2)
    assert order == ["question", "document"]
