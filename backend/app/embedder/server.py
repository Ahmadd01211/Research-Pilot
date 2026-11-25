"""Internal embedding service for open-weights Qwen3-Embedding.

Runs only on the private compose network. Weights for the pinned revision are fetched into
a named volume on first start and loaded from local files afterwards; submitted text is
never logged or sent anywhere.
"""

import math
import os
import threading
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
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


# Total characters encoded in one forward pass. Real chunks are about 1,000 characters, so
# a normal batch of 8 fits; longer inputs go one at a time. Attention memory grows with the
# square of sequence length, and 8 near-limit inputs together were OOM-killed at 4 GB.
BATCH_CHARS = 8_000


def batch_size(texts: list[str]) -> int:
    return len(texts) if sum(len(text) for text in texts) <= BATCH_CHARS else 1


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
            texts, batch_size=batch_size(texts), convert_to_numpy=True,
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
    # One inference at a time bounds memory; callers queue behind the lock.
    lock = threading.Lock()

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
        with lock:
            raw = encoder.encode(inputs)
        try:
            if len(raw) != len(inputs):
                raise ValueError("invalid batch")
            vectors = [truncated(row) for row in raw]
        except (TypeError, ValueError) as error:
            raise HTTPException(500, "The model returned an invalid embedding") from error
        return EmbedResponse(model=contract.MODEL, dimensions=contract.DIMENSIONS,
                             embeddings=vectors)

    return app
