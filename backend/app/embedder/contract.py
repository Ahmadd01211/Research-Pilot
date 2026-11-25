"""Shared contract between the backend and the internal embedding service.

Kept free of heavy imports so the backend can use it without PyTorch installed.
"""

MODEL = "Qwen/Qwen3-Embedding-0.6B"
# Pinned Hugging Face revision; changing it changes vectors, so bump FORMAT_VERSION too.
REVISION = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
# Qwen3-Embedding is trained with Matryoshka representation learning: the first 768 of its
# 1024 dimensions form a usable embedding, matching the existing vector(768) columns.
DIMENSIONS = 768
FORMAT_VERSION = "qwen3-0.6b-research-q1:mrl768:l2"
# Asymmetric retrieval: questions carry an instruction, passages are embedded as-is.
QUERY_INSTRUCTION = (
    "Instruct: Given a research question, retrieve passages from academic papers "
    "that answer it\nQuery: "
)
MAX_TEXTS = 8
MAX_CHARS = 8000
