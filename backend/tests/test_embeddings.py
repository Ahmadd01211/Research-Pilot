"""Provider contract and full database retrieval, with no external API calls."""

from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.core.config import Settings
from app.modules.documents import indexing, search
from app.modules.documents.chunks import CHUNKER_VERSION
from app.modules.documents.embeddings import (
    DIMENSIONS,
    EmbeddingFailure,
    GoogleEmbeddings,
)
from app.modules.documents.models import Document, DocumentIndex, DocumentPageText, EvidenceChunk
from app.modules.documents.processing import run_document
from app.modules.documents.reader import READER_VERSION
from tests.conftest import csrf, login, register
from tests.test_documents import upload
from tests.test_processing import setup
from tests.test_projects import authenticated, create


def test_google_format_shape_and_key_stay_server_side():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.endswith(":batchEmbedContents"):
            return httpx.Response(200, json={"embeddings": [{"values": [1.0] + [0.0] * 767}]})
        return httpx.Response(200, json={"embedding": {"values": [1.0] + [0.0] * 767}})

    settings = Settings(embedding_enabled=True, google_api_key=SecretStr("synthetic-secret"))
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        with GoogleEmbeddings(settings, http) as provider:
            assert len(provider.documents(["A source passage"])[0]) == DIMENSIONS
            assert provider.question("What was measured?")[0] == 1.0
    assert "synthetic-secret" not in str(calls)
    assert calls[0].headers["x-goog-api-key"] == "synthetic-secret"
    assert calls[0].url.host == "generativelanguage.googleapis.com"
    assert calls[0].read().find(b"title: none | text: A source passage") >= 0
    assert calls[1].read().find(b"task: question answering | query: What was measured?") >= 0


def test_provider_rejects_bad_vector():
    settings = Settings(embedding_enabled=True, google_api_key=SecretStr("synthetic-secret"))
    http = httpx.Client(transport=httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"embedding": {"values": [0.0] * 767}})
    ))
    with GoogleEmbeddings(settings, http) as provider, pytest.raises(EmbeddingFailure) as error:
        provider.question("What was measured?")
    assert error.value.code == "provider_shape"
    http.close()


def test_index_and_source_scoped_search(client, monkeypatch):
    authenticated(client)
    project_id = UUID(create(client)["id"])
    document_id = UUID(upload(client, str(project_id)).json()["document"]["id"])
    factory = client.app.state.session_factory
    with factory() as db:
        paper = db.get(Document, document_id)
        assert paper is not None and paper.processing is not None
        paper.processing.state = "extracted"
        db.add(DocumentPageText(
            document_id=document_id, page_number=1, text="Firm adoption was measured.",
            layout={"version": READER_VERSION},
        ))
        db.add(EvidenceChunk(
            id="synthetic-chunk", document_id=document_id, source_sha256=paper.sha256,
            reader_version=READER_VERSION, chunker_version=CHUNKER_VERSION,
            page_number=1, kind="prose", source_id="passage-1",
            text="Firm adoption was measured.", source_metadata={"passage_id": "passage-1"},
        ))
        db.commit()

    settings = Settings(embedding_enabled=True, google_api_key=SecretStr("synthetic-secret"))

    class FakeProvider:
        def __init__(self, _settings):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def documents(self, texts):
            assert texts == ["Firm adoption was measured."]
            return [[1.0] + [0.0] * 767]

        def question(self, _question):
            return [1.0] + [0.0] * 767

    monkeypatch.setattr(indexing, "GoogleEmbeddings", FakeProvider)
    monkeypatch.setattr(search, "GoogleEmbeddings", FakeProvider)
    with factory() as db:
        index = indexing.queue_index(db, _owner_id(db, project_id), project_id, document_id, settings)
        index_id = index.id
    indexing.run_index(factory, settings, index_id)
    with factory() as db:
        result = search.search(
            db, _owner_id(db, project_id), project_id,
            search.SearchRequest(question="What was measured?", document_ids=[document_id]),
            settings,
        )
        assert len(result.hits) == 1
        assert result.hits[0].page_number == 1
        assert result.hits[0].source_id == "passage-1"
        assert result.hits[0].reader_version == READER_VERSION
        assert db.get(indexing.DocumentIndex, index_id).state == "ready"


def test_hybrid_search_promotes_exact_table_terms_over_semantic_tie(client, monkeypatch):
    authenticated(client)
    project_id = UUID(create(client)["id"])
    document_id = UUID(upload(client, str(project_id)).json()["document"]["id"])
    factory = client.app.state.session_factory
    with factory() as db:
        paper = db.get(Document, document_id)
        assert paper is not None and paper.processing is not None
        paper.processing.state = "extracted"
        db.add(DocumentPageText(
            document_id=document_id, page_number=1, text="Table evidence.",
            layout={"version": READER_VERSION},
        ))
        for chunk_id, text in [
            ("a-semantic", "The paper studies firm adoption over time."),
            ("z-exact", "Table 7 | Funded by venture capital | Model 3: 0.1071"),
        ]:
            db.add(EvidenceChunk(
                id=chunk_id, document_id=document_id, source_sha256=paper.sha256,
                reader_version=READER_VERSION, chunker_version=CHUNKER_VERSION,
                page_number=1, kind="table_row", source_id=chunk_id,
                text=text, source_metadata={},
            ))
        db.commit()

    settings = Settings(embedding_enabled=True, google_api_key=SecretStr("synthetic-secret"))

    class TiedProvider:
        def __init__(self, _settings):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def documents(self, texts):
            return [[1.0] + [0.0] * 767 for _ in texts]

        def question(self, _question):
            return [1.0] + [0.0] * 767

    monkeypatch.setattr(indexing, "GoogleEmbeddings", TiedProvider)
    monkeypatch.setattr(search, "GoogleEmbeddings", TiedProvider)
    with factory() as db:
        index = indexing.queue_index(
            db, _owner_id(db, project_id), project_id, document_id, settings
        )
        index_id = index.id
    indexing.run_index(factory, settings, index_id)

    with factory() as db:
        result = search.search(
            db, _owner_id(db, project_id), project_id,
            search.SearchRequest(
                question="What is the venture capital coefficient in Table 7 model 3?",
                document_ids=[document_id], limit=2,
            ),
            settings,
        )
    assert [hit.chunk_id for hit in result.hits] == ["z-exact", "a-semantic"]


def test_extraction_automatically_queues_index_when_embeddings_are_configured(client):
    project_id, document_id, factory, storage = setup(client)
    settings = Settings(embedding_enabled=True, google_api_key=SecretStr("synthetic-secret"))

    # Extraction creates evidence chunks and the durable index job without a user action.
    run_document(factory, storage, document_id, settings)

    with factory() as db:
        indexes = db.scalars(
            select(DocumentIndex).where(DocumentIndex.document_id == document_id)
        ).all()
        assert len(indexes) == 1
        assert indexes[0].state == "queued"
        assert indexes[0].total_chunks > 0

    status = client.get(
        f"/api/v1/projects/{project_id}/documents/{document_id}/index"
    )
    assert status.status_code == 200
    assert status.json()["state"] == "queued"


def test_manual_index_request_refreshes_stale_reader_then_auto_queues(client):
    project_id, document_id, factory, storage = setup(client)
    settings = client.app.state.settings
    settings.embedding_enabled = True
    settings.google_api_key = SecretStr("synthetic-secret")
    run_document(factory, storage, document_id)
    with factory() as db:
        page = db.get(DocumentPageText, (document_id, 1))
        assert page is not None and page.layout is not None
        page.layout = {**page.layout, "version": "older-reader-version"}
        db.commit()

    response = client.post(
        f"/api/v1/projects/{project_id}/documents/{document_id}/index",
        headers=csrf(client),
    )
    assert response.status_code == 200
    assert response.json()["state"] == "preparing_reader"

    with factory() as db:
        paper = db.get(Document, document_id)
        assert paper is not None and paper.processing is not None
        assert paper.processing.state == "queued"
    run_document(factory, storage, document_id, settings)
    with factory() as db:
        paper = db.get(Document, document_id)
        assert paper is not None
        index = indexing.current_index(db, paper)
        assert index is not None and index.state == "queued"


def test_evidence_controls_are_owner_scoped_and_truthful_when_disabled(client):
    authenticated(client)
    project_id = create(client)["id"]
    document_id = upload(client, project_id).json()["document"]["id"]
    base = f"/api/v1/projects/{project_id}/evidence"
    assert client.get(base + "/capabilities").json() == {
        "embedding_enabled": False, "answer_enabled": False, "answer_model": "gemini-3.8-flash",
    }
    assert client.get(base + "/indexes").json() == {"items": []}
    assert client.post(base + "/answer", headers=csrf(client), json={
        "question": "What happened?", "document_ids": [document_id],
    }).status_code == 503
    assert client.get(f"/api/v1/projects/{project_id}/documents/{document_id}/index").json() is None
    register(client, "another-researcher@example.com")
    login(client, "another-researcher@example.com")
    for path in [base + "/capabilities", base + "/indexes", f"/api/v1/projects/{project_id}/documents/{document_id}/index"]:
        assert client.get(path).status_code == 404


def _owner_id(db, project_id):
    from app.modules.projects.models import ResearchProject

    project = db.get(ResearchProject, project_id)
    assert project is not None
    return project.owner_id
