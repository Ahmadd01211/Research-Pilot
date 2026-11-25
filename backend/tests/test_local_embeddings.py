"""Local Qwen3 embeddings: internal service contract and backend client. No model is loaded."""

import json
import math
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.embedder import contract
from app.embedder.server import create_app, slices
from app.modules.documents import embeddings, indexing
from app.modules.documents.chunks import CHUNKER_VERSION
from app.modules.documents.embeddings import EmbeddingFailure, LocalEmbeddings
from app.modules.documents.models import Document, DocumentPageText, EvidenceChunk
from app.modules.documents.reader import READER_VERSION
from tests.test_documents import upload
from tests.test_projects import authenticated, create

LOCAL = {"embedding_enabled": True, "embedding_provider": "local"}


class FakeEncoder:
    """Returns full-size 1024-d vectors so truncation and normalisation are observable."""

    def __init__(self) -> None:
        self.inputs: list[list[str]] = []

    def encode(self, texts: list[str]) -> list[list[float]]:
        self.inputs.append(texts)
        vector = [3.0, 4.0] + [0.0] * 1022
        vector[900] = 100.0  # beyond the 768-d Matryoshka prefix: must be dropped
        return [vector for _ in texts]


def embedder(encoder: FakeEncoder) -> TestClient:
    return TestClient(create_app(lambda: encoder))


def test_local_provider_needs_no_key_and_reports_qwen():
    settings = Settings(**LOCAL)
    assert embeddings.embeddings_configured(settings)
    assert settings.embedding_model == contract.MODEL == "Qwen/Qwen3-Embedding-0.6B"
    spec = embeddings.spec_for(settings)
    assert (spec.provider, spec.dimensions) == ("local", 768)
    assert spec.format_version != embeddings.spec_for(Settings()).format_version
    with pytest.raises(ValueError):
        Settings(**LOCAL, embedding_url="ftp://embedder")
    with pytest.raises(ValueError):
        Settings(**LOCAL, embedding_url="http://user:secret@embedder:8000")


def test_embedder_truncates_normalises_and_instructs_only_questions():
    encoder = FakeEncoder()
    with embedder(encoder) as client:
        assert client.get("/health").json() == {"status": "ready", "model": contract.MODEL}
        documents = client.post("/v1/embed", json={"kind": "document", "texts": ["A passage."]})
        query = client.post("/v1/embed", json={"kind": "query", "texts": ["What was measured?"]})
    assert documents.status_code == query.status_code == 200
    body = documents.json()
    assert body["model"] == contract.MODEL and body["dimensions"] == 768
    vector = body["embeddings"][0]
    assert len(vector) == 768
    assert vector[:2] == pytest.approx([0.6, 0.8])
    assert math.isclose(math.sqrt(sum(value * value for value in vector)), 1.0)
    # Qwen3 is asymmetric: questions carry a retrieval instruction, passages do not.
    assert encoder.inputs[0] == ["A passage."]
    assert encoder.inputs[1] == [contract.QUERY_INSTRUCTION + "What was measured?"]


@pytest.mark.parametrize("texts", [[], ["x"] * 9, [""], ["   "], ["x" * 8001]])
def test_embedder_rejects_unbounded_input(texts):
    encoder = FakeEncoder()
    with embedder(encoder) as client:
        response = client.post("/v1/embed", json={"kind": "document", "texts": texts})
    assert response.status_code == 422
    assert encoder.inputs == []


def test_long_inputs_are_encoded_one_at_a_time_to_bound_memory():
    # Live finding: 8 near-limit chunks in one forward pass exceeded a 4 GB limit (OOM kill).
    assert slices(["x" * 8000] + ["short"] * 7)[0] == ["x" * 8000]
    assert all(len(part) == 1 for part in slices(["x" * 2000] * 8))


def test_embedder_refuses_invalid_model_output():
    class Broken(FakeEncoder):
        def encode(self, texts: list[str]) -> list[list[float]]:
            return [[math.nan] * 1024 for _ in texts]

    with TestClient(create_app(Broken)) as client:
        response = client.post("/v1/embed", json={"kind": "document", "texts": ["A passage."]})
    assert response.status_code == 500
    assert "nan" not in response.text.lower()


def local_client(handler) -> tuple[LocalEmbeddings, list[httpx.Request]]:
    captured: list[httpx.Request] = []

    def recording(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return handler(request)

    http = httpx.Client(transport=httpx.MockTransport(recording))
    return LocalEmbeddings(Settings(**LOCAL), http), captured


def reply(count: int, model: str = contract.MODEL) -> httpx.Response:
    return httpx.Response(200, json={
        "model": model, "dimensions": 768, "embeddings": [[2.0] + [0.0] * 767] * count,
    })


def test_local_client_posts_to_internal_service_and_normalises():
    provider, captured = local_client(lambda request: reply(len(json.loads(request.read())["texts"])))
    with provider:
        vectors = provider.documents(["First passage.", "Second passage."])
        question = provider.question("  What was measured?  ")
    assert [vector[0] for vector in vectors] == [1.0, 1.0] and question[0] == 1.0
    assert str(captured[0].url) == "http://embedder:8000/v1/embed"
    assert json.loads(captured[0].read()) == {
        "kind": "document", "texts": ["First passage.", "Second passage."],
    }
    assert json.loads(captured[1].read()) == {"kind": "query", "texts": ["What was measured?"]}


@pytest.mark.parametrize("response,code,transient", [
    (httpx.Response(503), "provider_unavailable", True),
    (httpx.Response(422, json={}), "provider_rejected", False),
    (None, "provider_shape", False),  # another model's vectors are a different space
])
def test_local_client_failures_are_classified(response, code, transient):
    provider, _ = local_client(lambda _request: response or reply(1, model="other/model"))
    with provider, pytest.raises(EmbeddingFailure) as error:
        provider.question("What was measured?")
    assert (error.value.code, error.value.transient) == (code, transient)


def test_unreachable_embedder_is_transient():
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    provider, _ = local_client(refuse)
    with provider, pytest.raises(EmbeddingFailure) as error:
        provider.documents(["A passage."])
    assert error.value.transient


def test_index_identity_follows_the_provider(client, monkeypatch):
    authenticated(client)
    project_id = UUID(create(client)["id"])
    document_id = UUID(upload(client, str(project_id)).json()["document"]["id"])
    factory = client.app.state.session_factory
    with factory() as db:
        paper = db.get(Document, document_id)
        assert paper is not None and paper.processing is not None
        paper.processing.state = "extracted"
        db.add(DocumentPageText(document_id=document_id, page_number=1, text="Text.",
                                layout={"version": READER_VERSION}))
        db.add(EvidenceChunk(
            id="local-chunk", document_id=document_id, source_sha256=paper.sha256,
            reader_version=READER_VERSION, chunker_version=CHUNKER_VERSION, page_number=1,
            kind="prose", source_id="passage-1", text="Text.", source_metadata={},
        ))
        db.commit()
    from tests.test_embeddings import _owner_id

    local = Settings(**LOCAL)
    with factory() as db:
        owner = _owner_id(db, project_id)
        index = indexing.queue_index(db, owner, project_id, document_id, local)
        assert index is not None
        assert (index.provider, index.model, index.dimensions) == ("local", contract.MODEL, 768)
        paper = db.get(Document, document_id)
        assert paper is not None
        # Vectors from different models are never mixed: Google sees no current index.
        assert indexing.current_index(db, paper, local) is not None
        assert indexing.current_index(db, paper, Settings()) is None


def test_model_is_fetched_once_per_pinned_revision(tmp_path):
    from app.embedder.models import ensure_model

    calls: list[tuple[str, str, str]] = []

    def download(repo: str, revision: str, target: str) -> None:
        calls.append((repo, revision, target))
        (tmp_path / contract.REVISION / "config.json").write_text("{}")

    path = ensure_model(tmp_path, download)
    assert path == tmp_path / contract.REVISION
    assert calls == [(contract.MODEL, contract.REVISION, str(path))]
    # A later start (or a rebuilt image) reuses the volume without any network call.
    assert ensure_model(tmp_path, download) == path
    assert len(calls) == 1


def test_interrupted_download_is_never_treated_as_complete(tmp_path):
    from app.embedder.models import ensure_model

    def broken(_repo: str, _revision: str, target: str) -> None:
        (tmp_path / contract.REVISION / "model.safetensors").write_text("partial")
        raise OSError("connection reset")

    with pytest.raises(OSError):
        ensure_model(tmp_path, broken)
    retried: list[str] = []
    ensure_model(tmp_path, lambda _r, _v, target: retried.append(target))
    assert retried == [str(tmp_path / contract.REVISION)]
