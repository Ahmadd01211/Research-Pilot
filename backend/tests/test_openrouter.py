"""OpenRouter answers and the shared daily answer budget; no real provider calls."""

import json
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from pydantic import SecretStr
from redis import Redis

from app.core.config import Settings
from app.modules.documents import answers, budget
from app.modules.documents.search import SearchHit

MODEL = "meta-llama/llama-3.3-70b-instruct:free"


def settings(**extra) -> Settings:
    values = {
        "answer_enabled": True,
        "answer_provider": "openrouter",
        "answer_model": MODEL,
        "openrouter_api_key": SecretStr("synthetic-openrouter-key"),
        "rate_namespace": "rp:test:" + str(uuid4()),
    }
    values.update(extra)
    return Settings(**values)


def source() -> answers.AnswerSource:
    return answers.AnswerSource(id="S1", hit=SearchHit(
        chunk_id="chunk-1", document_id=uuid4(), source_sha256="a" * 64,
        reader_version="v1", page_number=2, kind="prose", source_id="passage-1",
        text="The survey covered 850,000 firms.", source_metadata={}, distance=0.2,
    ))


def mock_provider(monkeypatch, handler) -> list[httpx.Request]:
    captured: list[httpx.Request] = []

    def recording(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return handler(request)

    real_client = httpx.Client
    monkeypatch.setattr(answers.httpx, "Client", lambda **_kwargs: real_client(
        transport=httpx.MockTransport(recording),
    ))
    return captured


def completion(content: str, finish: str = "stop") -> httpx.Response:
    return httpx.Response(200, json={
        "choices": [{"finish_reason": finish, "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150},
    })


def test_openrouter_requires_server_key_and_valid_model():
    with pytest.raises(ValueError):
        Settings(answer_enabled=True, answer_provider="openrouter", answer_model=MODEL)
    with pytest.raises(ValueError):
        settings(answer_model="not a model")
    assert settings().answer_model == MODEL


def test_openrouter_answer_is_cited_and_keeps_key_server_side(monkeypatch):
    output = {"insufficient_evidence": False, "statements": [
        {"text": "The survey covered 850,000 firms.", "source_ids": ["S1"]}]}
    captured = mock_provider(
        monkeypatch, lambda _r: completion("```json\n" + json.dumps(output) + "\n```")
    )
    result = answers._generate(settings(), "How many firms?", [source()], [])
    assert result.statements[0].source_ids == ["S1"]
    request = captured[0]
    assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer synthetic-openrouter-key"
    body = json.loads(request.read())
    assert body["model"] == MODEL and body["temperature"] == 0
    # Private papers: ask OpenRouter to route only to hosts that do not collect prompts.
    assert body["provider"] == {"data_collection": "deny"}
    # Models must be told the exact shape; a real model answered with "evidence_ids".
    schema = body["response_format"]["json_schema"]["schema"]
    assert body["response_format"]["type"] == "json_schema"
    assert schema["properties"]["statements"]["items"]["required"] == ["text", "source_ids"]
    assert '"source_ids"' in body["messages"][0]["content"]
    assert "850,000 firms" in body["messages"][1]["content"]


def test_openrouter_uncited_claims_are_rejected(monkeypatch):
    output = {"insufficient_evidence": False, "statements": [
        {"text": "Unsupported claim.", "source_ids": ["S7"]}]}
    mock_provider(monkeypatch, lambda _r: completion(json.dumps(output)))
    with pytest.raises(HTTPException) as error:
        answers._generate(settings(), "How many firms?", [source()], [])
    assert error.value.status_code == 502


@pytest.mark.parametrize("response,status", [
    (httpx.Response(429, json={"error": {"message": "limit"}}), 503),
    (completion("not json at all"), 502),
    (completion("{}", finish="length"), 502),
])
def test_openrouter_failures_are_honest(monkeypatch, response, status):
    mock_provider(monkeypatch, lambda _r: response)
    with pytest.raises(HTTPException) as error:
        answers._generate(settings(), "How many firms?", [source()], [])
    assert error.value.status_code == status


def test_daily_answer_budget_is_shared_and_enforced():
    config = settings(answer_daily_limit=2)
    redis = Redis.from_url(config.redis_url.get_secret_value())
    assert budget.remaining(redis, config) == 2
    budget.reserve(redis, config, "user-a")
    budget.reserve(redis, config, "user-b")
    assert budget.remaining(redis, config) == 0
    with pytest.raises(HTTPException) as error:
        budget.reserve(redis, config, "user-c")
    assert error.value.status_code == 429
    assert "daily" in error.value.detail
    assert 0 < int(error.value.headers["Retry-After"]) <= 86400
    assert budget.remaining(redis, config) == 0


def test_one_user_cannot_spend_the_whole_shared_budget():
    config = settings(answer_daily_limit=10, answer_user_daily_limit=2)
    redis = Redis.from_url(config.redis_url.get_secret_value())
    budget.reserve(redis, config, "user-a")
    budget.reserve(redis, config, "user-a")
    with pytest.raises(HTTPException) as error:
        budget.reserve(redis, config, "user-a")
    assert error.value.status_code == 429 and "your daily" in error.value.detail
    assert budget.remaining(redis, config) == 8  # the refused attempt reserved nothing
    budget.reserve(redis, config, "user-b")
    assert budget.remaining(redis, config) == 7


def test_empty_user_limit_from_compose_means_unset(monkeypatch):
    # compose passes ${RP_ANSWER_USER_DAILY_LIMIT:-} as an empty string.
    monkeypatch.setenv("RP_ANSWER_USER_DAILY_LIMIT", "")
    assert Settings().answer_user_limit == 20


def test_user_limit_defaults_to_the_global_limit_and_cannot_exceed_it():
    assert settings(answer_daily_limit=20).answer_user_limit == 20
    with pytest.raises(ValueError):
        settings(answer_daily_limit=5, answer_user_daily_limit=6)


def test_data_collection_can_be_allowed_explicitly(monkeypatch):
    output = {"insufficient_evidence": True, "statements": []}
    captured = mock_provider(monkeypatch, lambda _r: completion(json.dumps(output)))
    answers._generate(
        settings(openrouter_allow_data_collection=True), "Q?", [source()], []
    )
    assert "provider" not in json.loads(captured[0].read())


def test_uppercase_json_fence_is_accepted(monkeypatch):
    output = {"insufficient_evidence": True, "statements": []}
    fenced = "```JSON\n" + json.dumps(output) + "\n```"
    mock_provider(monkeypatch, lambda _r: completion(fenced))
    assert answers._generate(settings(), "Q?", [source()], []).insufficient_evidence
