"""Internal embedding service for open-weights Qwen3-Embedding.

Runs only on the private compose network. Weights for the pinned revision are fetched into
a named volume on first start and loaded from local files afterwards; submitted text is
never logged or sent anywhere.
"""

import math
import os
import threading
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Literal, Protocol

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.embedder import contract
from app.embedder.models import ensure_model


class Encoder(Protocol):
    def encode(self, texts: list[str]) -> list[list[float]]: ...


class EmbedRequest(BaseModel):
    kind: Literal["document", "query"]
    texts: list[str] = Field(min_length=1, max_length=contract.MAX_TEXTS)

    @field_validator("texts")
    @classmethod
    def bounded(cls, texts: list[str]) -> list[str]:
        if any(not text.strip() or len(text) > contract.MAX_CHARS for text in texts):
            raise ValueError(f"Each text must be 1–{contract.MAX_CHARS} characters")
        return texts


class EmbedResponse(BaseModel):
    model: str
    dimensions: int
    embeddings: list[list[float]]


def truncated(values: list[float]) -> list[float]:
    """Matryoshka prefix, then unit length so cosine distance is meaningful."""
    vector = [float(value) for value in values[: contract.DIMENSIONS]]
    if len(vector) != contract.DIMENSIONS or not all(math.isfinite(value) for value in vector):
        raise ValueError("invalid vector")
    norm = math.sqrt(sum(value * value for value in vector))
    if norm < 1e-8:
        raise ValueError("invalid vector")
    return [value / norm for value in vector]


# Characters per document forward pass. A slice of ~2 real chunks takes ~2 s on 4 CPU threads,
# so a question never waits behind a whole 8-chunk batch (8 s, or 70 s+ at the limit).
# Longer texts go alone: attention memory grows with the square of length, and 8
# near-limit inputs in one pass were OOM-killed at 4 GB.
SLICE_CHARS = 2_000


def slices(texts: list[str]) -> list[list[str]]:
    parts: list[list[str]] = []
    for text in texts:
        if parts and sum(len(item) for item in parts[-1]) + len(text) <= SLICE_CHARS:
            parts[-1].append(text)
        else:
            parts.append([text])
    return parts


class PriorityGate:
    """One inference at a time; waiting questions go before waiting document slices."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._busy = False
        self._questions_waiting = 0

    @contextmanager
    def hold(self, query: bool) -> Iterator[None]:
        with self._condition:
            if query:
                self._questions_waiting += 1
            try:
                self._condition.wait_for(
                    lambda: not self._busy and (query or self._questions_waiting == 0)
                )
            finally:
                if query:
                    self._questions_waiting -= 1
            self._busy = True
        try:
            yield
        finally:
            with self._condition:
                self._busy = False
                self._condition.notify_all()


class SentenceTransformerEncoder:
    def __init__(self, path: str, threads: int):
        import torch
        from sentence_transformers import SentenceTransformer

        torch.set_num_threads(threads)
        self.model = SentenceTransformer(path, device="cpu", local_files_only=True)
        # Chunks are at most 8000 characters; 2048 tokens covers them without truncation.
        self.model.max_seq_length = 2048

    def encode(self, texts: list[str]) -> list[list[float]]:
        output = self.model.encode(
            texts, batch_size=len(texts), convert_to_numpy=True,
            normalize_embeddings=False,
        )
        return [[float(value) for value in row] for row in output.tolist()]


def load_encoder() -> Encoder:
    # First start downloads the pinned revision into the volume; later starts are offline.
    path = ensure_model(Path(os.environ.get("EMBEDDER_MODEL_ROOT", "/models")))
    return SentenceTransformerEncoder(
        str(path),
        max(1, int(os.environ.get("EMBEDDER_THREADS", str(os.cpu_count() or 1)))),
    )


def create_app(encoder_factory: Callable[[], Encoder] = load_encoder) -> FastAPI:
    state: dict[str, Encoder] = {}
    gate = PriorityGate()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        state["encoder"] = encoder_factory()
        yield
        state.clear()

    app = FastAPI(title="ResearchPilot embedder", lifespan=lifespan, docs_url=None,
                  redoc_url=None, openapi_url=None)

    @app.get("/health")
    def health() -> dict[str, str]:
        if "encoder" not in state:
            raise HTTPException(503, "Model is loading")
        return {"status": "ready", "model": contract.MODEL}

    @app.post("/v1/embed", response_model=EmbedResponse)
    def embed(request: EmbedRequest) -> EmbedResponse:
        encoder = state.get("encoder")
        if encoder is None:
            raise HTTPException(503, "Model is loading")
        inputs = request.texts if request.kind == "document" else [
            contract.QUERY_INSTRUCTION + text.strip() for text in request.texts
        ]
        raw: list[list[float]] = []
        if request.kind == "query":
            with gate.hold(query=True):
                raw = encoder.encode(inputs)
        else:
            # Release the gate between slices so a waiting question can run.
            for part in slices(inputs):
                with gate.hold(query=False):
                    raw.extend(encoder.encode(part))
        try:
            if len(raw) != len(inputs):
                raise ValueError("invalid batch")
            vectors = [truncated(row) for row in raw]
        except (TypeError, ValueError) as error:
            raise HTTPException(500, "The model returned an invalid embedding") from error
        return EmbedResponse(model=contract.MODEL, dimensions=contract.DIMENSIONS,
                             embeddings=vectors)

    return app
