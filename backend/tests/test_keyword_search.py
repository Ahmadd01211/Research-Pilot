"""Keyword retrieval works without embeddings; answers spend the shared daily budget."""

import json

import httpx
from pydantic import SecretStr
from sqlalchemy import text

from app.modules.documents import answers
from app.modules.documents.processing import run_document
from tests.conftest import csrf, login, register
from tests.test_processing import setup

MODEL = "meta-llama/llama-3.3-70b-instruct:free"


def openrouter(client, limit=20):
    settings = client.app.state.settings
    settings.answer_enabled = True
    settings.answer_provider = "openrouter"
    settings.answer_model = MODEL
    settings.openrouter_api_key = SecretStr("synthetic-openrouter-key")
    settings.answer_daily_limit = limit
    return settings


def fake_completion(monkeypatch, calls):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        output = {"insufficient_evidence": False, "statements": [
            {"text": "The second page reports a different finding.", "source_ids": ["S1"]}]}
        return httpx.Response(200, json={"choices": [
            {"finish_reason": "stop", "message": {"content": json.dumps(output)}}]})

    real_client = httpx.Client
    monkeypatch.setattr(answers.httpx, "Client", lambda **_kwargs: real_client(
        transport=httpx.MockTransport(handler)))


def test_keyword_search_needs_no_embeddings_and_is_labelled(client):
    project, document, factory, storage = setup(client)
    base = f"/api/v1/projects/{project}/evidence"
    status = client.get(base + "/indexes").json()["items"]
    assert status == []  # not extracted yet: nothing is claimed searchable
    run_document(factory, storage, document)

    capabilities = client.get(base + "/capabilities").json()
    assert capabilities["search_mode"] == "keyword" and not capabilities["embedding_enabled"]
    [item] = client.get(base + "/indexes").json()["items"]
    assert item["document_id"] == str(document) and item["state"] == "ready"
    assert item["search_mode"] == "keyword"
    assert item["processed_chunks"] == item["total_chunks"] > 0

    result = client.post(base + "/search", headers=csrf(client), json={
        "question": "Which page reports a different finding?", "document_ids": [str(document)],
    })
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["model"] == "postgres-full-text" and body["index_format"] == "keyword-v1"
    assert body["hits"][0]["page_number"] == 2

    register(client, "outsider@example.com")
    login(client, "outsider@example.com")
    assert client.post(base + "/search", headers=csrf(client), json={
        "question": "finding", "document_ids": [str(document)],
    }).status_code == 404


def test_keyword_mode_explains_stale_papers_and_can_refresh_them(client):
    from app.modules.documents.models import DocumentPageText

    project, document, factory, storage = setup(client)
    run_document(factory, storage, document)
    with factory() as db:  # simulate a paper extracted by an older reader release
        for page in db.query(DocumentPageText).filter_by(document_id=document):
            page.layout = {**(page.layout or {}), "version": "word-passages-v1:old"}
        db.execute(
            text("DELETE FROM evidence_chunks WHERE document_id = :d"),
            {"d": document},
        )
        db.commit()
    base = f"/api/v1/projects/{project}/evidence"
    [item] = client.get(base + "/indexes").json()["items"]
    assert item["state"] == "needs_refresh" and item["search_mode"] == "keyword"

    refresh = client.post(
        f"/api/v1/projects/{project}/documents/{document}/index", headers=csrf(client)
    )
    assert refresh.status_code == 200, refresh.text
    assert refresh.json()["state"] == "preparing_reader"
    run_document(factory, storage, document)
    [item] = client.get(base + "/indexes").json()["items"]
    assert item["state"] == "ready" and item["total_chunks"] > 0


def test_keyword_mode_reports_papers_without_eligible_evidence(client):
    project, document, factory, storage = setup(client)
    run_document(factory, storage, document)
    with factory() as db:
        db.execute(
            text("DELETE FROM evidence_chunks WHERE document_id = :d"),
            {"d": document},
        )
        db.commit()
    [item] = client.get(f"/api/v1/projects/{project}/evidence/indexes").json()["items"]
    assert item["state"] == "no_evidence" and item["total_chunks"] == 0


def test_capabilities_survive_a_redis_outage(client, monkeypatch):
    from redis.exceptions import ConnectionError as RedisConnectionError

    from app.modules.documents import budget

    project, _document, _factory, _storage = setup(client)
    openrouter(client)

    def down(*_args, **_kwargs):
        raise RedisConnectionError("redis unavailable")

    monkeypatch.setattr(budget, "remaining", down)
    response = client.get(f"/api/v1/projects/{project}/evidence/capabilities")
    assert response.status_code == 200
    assert response.json()["search_mode"] == "keyword"
    assert response.json()["answers_remaining_today"] is None


def test_openrouter_answer_uses_keyword_evidence_and_daily_budget(client, monkeypatch):
    project, document, factory, storage = setup(client)
    run_document(factory, storage, document)
    openrouter(client, limit=1)
    calls: list[httpx.Request] = []
    fake_completion(monkeypatch, calls)
    base = f"/api/v1/projects/{project}/evidence"
    capabilities = client.get(base + "/capabilities").json()
    assert capabilities["answer_enabled"] and capabilities["answers_remaining_today"] == 1
    assert capabilities["answer_data_policy"] == "no_collection"

    question = {"question": "What does the second page report?", "document_ids": [str(document)]}
    first = client.post(base + "/answer", headers=csrf(client), json=question)
    assert first.status_code == 200, first.text
    assert first.json()["statements"][0]["source_ids"] == ["S1"]
    assert first.json()["model"] == MODEL
    assert client.get(base + "/capabilities").json()["answers_remaining_today"] == 0

    second = client.post(base + "/answer", headers=csrf(client), json=question)
    assert second.status_code == 429 and "daily" in second.json()["detail"]
    assert len(calls) == 1  # the exhausted budget never reaches the provider


def test_question_without_evidence_does_not_spend_budget(client, monkeypatch):
    project, document, factory, storage = setup(client)
    run_document(factory, storage, document)
    openrouter(client, limit=1)
    calls: list[httpx.Request] = []
    fake_completion(monkeypatch, calls)
    base = f"/api/v1/projects/{project}/evidence"
    result = client.post(base + "/answer", headers=csrf(client), json={
        "question": "zebra quasar xylophone", "document_ids": [str(document)],
    })
    assert result.status_code == 200 and result.json()["insufficient_evidence"]
    assert calls == []
    assert client.get(base + "/capabilities").json()["answers_remaining_today"] == 1
