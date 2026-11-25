"""Model weights live in a named volume, fetched once per pinned revision.

Rebuilding or deleting the image never re-downloads them. A completion marker is written
only after a successful download, so an interrupted fetch resumes on the next start.
"""

from collections.abc import Callable
from pathlib import Path

from app.embedder import contract

Downloader = Callable[[str, str, str], None]
MARKER = ".complete"


def hugging_face(repo: str, revision: str, target: str) -> None:
    from huggingface_hub import snapshot_download

    snapshot_download(repo, revision=revision, local_dir=target)


def ensure_model(root: Path, download: Downloader = hugging_face) -> Path:
    path = root / contract.REVISION
    if (path / MARKER).is_file():
        return path
    path.mkdir(parents=True, exist_ok=True)
    download(contract.MODEL, contract.REVISION, str(path))
    (path / MARKER).write_text(contract.REVISION, encoding="utf-8")
    return path
