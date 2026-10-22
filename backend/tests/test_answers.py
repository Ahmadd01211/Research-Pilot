"""Cited-answer boundary tests with a fake provider; no user data leaves the test."""

import json
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from app.core.config import Settings
from app.modules.documents import answers
from app.modules.documents.search import SearchHit


def source() -> answers.AnswerSource:
    return answers.AnswerSource(id="S1", hit=SearchHit(
        chunk_id="chunk-1", document_id=uuid4(), source_sha256="a" * 64,
        reader_version="v1", page_number=2, kind="prose", source_id="passage-1",
        text="The survey covered 850,000 firms.", source_metadata={}, distance=0.2,
    ))


@pytest.mark.parametrize("source_ids,valid", [(["S1"], True), (["S9"], False), (["S1", "S1"], False)])
def test_answer_accepts_only_retrieved_citations(monkeypatch, source_ids, valid):
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        output = {"insufficient_evidence": False, "statements": [
            {"text": "The survey covered 850,000 firms.", "source_ids": source_ids},
        ]}
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {
            "parts": [{"text": json.dumps(output)}],
        }}]})

    real_client = httpx.Client
    monkeypatch.setattr(answers.httpx, "Client", lambda **_kwargs: real_client(
        transport=httpx.MockTransport(handler),
    ))
    settings = Settings(answer_enabled=True, google_api_key=SecretStr("synthetic-secret"))
    if valid:
        result = answers._generate(settings, "How many firms?", [source()], [])
        assert result.statements[0].source_ids == ["S1"]
    else:
        with pytest.raises(HTTPException) as error:
            answers._generate(settings, "How many firms?", [source()], [])
        assert error.value.status_code == 502
    assert captured[0].headers["x-goog-api-key"] == "synthetic-secret"
    assert b"850,000 firms" in captured[0].read()
    assert "synthetic-secret" not in str(captured)


def test_answer_abstention_discards_uncited_text(monkeypatch):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {
            "parts": [{"text": json.dumps({"insufficient_evidence": True,
                                      "statements": [{"text": "Unsupported", "source_ids": ["S1"]}]})}],
        }}]})

    real_client = httpx.Client
    monkeypatch.setattr(answers.httpx, "Client", lambda **_kwargs: real_client(
        transport=httpx.MockTransport(handler),
    ))
    settings = Settings(answer_enabled=True, google_api_key=SecretStr("synthetic-secret"))
    result = answers._generate(settings, "Unknown?", [source()], [])
    assert result.insufficient_evidence and not result.statements
