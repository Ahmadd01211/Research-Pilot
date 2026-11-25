"""Bounded text embeddings from Google or the internal Qwen3 service.

Credentials stay server-side; the local provider keeps source text on this server.
"""

import math
from collections.abc import Sequence
from typing import NamedTuple, Protocol

import httpx

from app.core.config import Settings
from app.embedder import contract as local
from app.modules.documents.provider_usage import record_usage

MODEL = "gemini-embedding-2"
DIMENSIONS = 768
FORMAT_VERSION = "gemini2-qa-v1:l2"
API = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2"


class EmbeddingSpec(NamedTuple):
    """Identity of a vector space. Indexes from different specs are never mixed."""

    provider: str
    model: str
    dimensions: int
    format_version: str


GOOGLE = EmbeddingSpec("google", MODEL, DIMENSIONS, FORMAT_VERSION)
LOCAL = EmbeddingSpec("local", local.MODEL, local.DIMENSIONS, local.FORMAT_VERSION)


def spec_for(settings: Settings) -> EmbeddingSpec:
    return LOCAL if settings.embedding_provider == "local" else GOOGLE


def embeddings_configured(settings: Settings) -> bool:
    if not settings.embedding_enabled:
        return False
    if settings.embedding_provider == "local":
        return True
    return bool(settings.google_api_key and settings.google_api_key.get_secret_value().strip())


class EmbeddingFailure(Exception):
    def __init__(self, code: str, transient: bool):
        super().__init__(code)
        self.code = code
        self.transient = transient


def document_input(text: str) -> str:
    return f"title: none | text: {text}"


def question_input(question: str) -> str:
    return f"task: question answering | query: {question}"


def normalized(values: object) -> list[float]:
    if not isinstance(values, list) or len(values) != DIMENSIONS:
        raise EmbeddingFailure("provider_shape", False)
    if any(type(value) not in (float, int) or not math.isfinite(value) for value in values):
        raise EmbeddingFailure("provider_shape", False)
    vector = [float(value) for value in values]
    norm = math.sqrt(sum(value * value for value in vector))
    if norm < 1e-8:
        raise EmbeddingFailure("provider_shape", False)
    return [value / norm for value in vector]


def vector_literal(values: Sequence[float]) -> str:
    if len(values) != DIMENSIONS or any(not math.isfinite(value) for value in values):
        raise ValueError("Invalid vector")
    return "[" + ",".join(format(value, ".9g") for value in values) + "]"


class GoogleEmbeddings:
    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        if not settings.embedding_enabled or settings.google_api_key is None:
            raise EmbeddingFailure("provider_not_configured", False)
        self.key = settings.google_api_key.get_secret_value()
        self.client = client or httpx.Client(timeout=httpx.Timeout(20.0))
        self.owns_client = client is None

    def __enter__(self) -> "GoogleEmbeddings":
        return self

    def __exit__(self, *_args: object) -> None:
        if self.owns_client:
            self.client.close()

    def _post(self, action: str, body: dict[str, object]) -> dict[str, object]:
        try:
            response = self.client.post(
                f"{API}:{action}",
                headers={"x-goog-api-key": self.key, "content-type": "application/json"},
                json=body,
            )
        except httpx.RequestError as error:
            record_usage(action, MODEL, 0, None)
            raise EmbeddingFailure("provider_unavailable", True) from error
        if response.status_code >= 400:
            record_usage(action, MODEL, response.status_code, None)
        if response.status_code == 429 or response.status_code >= 500:
            raise EmbeddingFailure("provider_unavailable", True)
        if response.status_code >= 400:
            raise EmbeddingFailure("provider_rejected", False)
        try:
            data = response.json()
        except ValueError as error:
            raise EmbeddingFailure("provider_shape", False) from error
        if not isinstance(data, dict):
            raise EmbeddingFailure("provider_shape", False)
        record_usage(action, MODEL, response.status_code, data)
        return data

    def documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not 1 <= len(texts) <= 8 or any(not text or len(text) > 8000 for text in texts):
            raise ValueError("Embedding batch must contain 1–8 bounded source chunks")
        requests = [
            {
                "model": f"models/{MODEL}",
                "content": {"parts": [{"text": document_input(text)}]},
                "output_dimensionality": DIMENSIONS,
            }
            for text in texts
        ]
        data = self._post("batchEmbedContents", {"requests": requests})
        embeddings = data.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise EmbeddingFailure("provider_shape", False)
        return [normalized(item.get("values") if isinstance(item, dict) else None) for item in embeddings]

    def question(self, question: str) -> list[float]:
        if not 1 <= len(question.strip()) <= 500:
            raise ValueError("Question must be 1–500 characters")
        data = self._post(
            "embedContent",
            {
                "model": f"models/{MODEL}",
                "content": {"parts": [{"text": question_input(question.strip())}]},
                "output_dimensionality": DIMENSIONS,
            },
        )
        embedding = data.get("embedding")
        return normalized(embedding.get("values") if isinstance(embedding, dict) else None)


def check_documents(texts: Sequence[str]) -> None:
    if not 1 <= len(texts) <= local.MAX_TEXTS or any(
        not text.strip() or len(text) > local.MAX_CHARS for text in texts
    ):
        raise ValueError("Embedding batch must contain 1–8 bounded source chunks")


class LocalEmbeddings:
    """Client for the internal embedder container; no key, no third party."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        if not settings.embedding_enabled or settings.embedding_provider != "local":
            raise EmbeddingFailure("provider_not_configured", False)
        self.url = settings.embedding_url.rstrip("/") + "/v1/embed"
        # CPU inference queues behind one lock; stay inside the 90 s index lease.
        self.client = client or httpx.Client(timeout=httpx.Timeout(80.0, connect=5.0))
        self.owns_client = client is None

    def __enter__(self) -> "LocalEmbeddings":
        return self

    def __exit__(self, *_args: object) -> None:
        if self.owns_client:
            self.client.close()

    def _embed(self, kind: str, texts: list[str]) -> list[list[float]]:
        try:
            response = self.client.post(self.url, json={"kind": kind, "texts": texts})
        except httpx.RequestError as error:
            raise EmbeddingFailure("provider_unavailable", True) from error
        if response.status_code == 429 or response.status_code >= 500:
            raise EmbeddingFailure("provider_unavailable", True)
        if response.status_code >= 400:
            raise EmbeddingFailure("provider_rejected", False)
        try:
            data = response.json()
        except ValueError as error:
            raise EmbeddingFailure("provider_shape", False) from error
        if (
            not isinstance(data, dict) or data.get("model") != local.MODEL
            or data.get("dimensions") != local.DIMENSIONS
            or not isinstance(data.get("embeddings"), list)
            or len(data["embeddings"]) != len(texts)
        ):
            raise EmbeddingFailure("provider_shape", False)
        return [normalized(values) for values in data["embeddings"]]

    def documents(self, texts: Sequence[str]) -> list[list[float]]:
        check_documents(texts)
        return self._embed("document", list(texts))

    def question(self, question: str) -> list[float]:
        if not 1 <= len(question.strip()) <= 500:
            raise ValueError("Question must be 1–500 characters")
        return self._embed("query", [question.strip()])[0]


class EmbeddingProvider(Protocol):
    def __enter__(self) -> "EmbeddingProvider": ...

    def __exit__(self, *_args: object) -> None: ...

    def documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def question(self, question: str) -> list[float]: ...


def provider_for(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "local":
        return LocalEmbeddings(settings)
    return GoogleEmbeddings(settings)
