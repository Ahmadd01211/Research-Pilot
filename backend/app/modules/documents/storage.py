"""Private local adapter: callers never supply a filesystem key."""

import os
from pathlib import Path
from uuid import UUID, uuid4


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def prepare(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        (self.root / "staging").mkdir(exist_ok=True, mode=0o700)
        (self.root / "papers").mkdir(exist_ok=True, mode=0o700)

    def stage(self) -> Path:
        self.prepare()
        return self.root / "staging" / str(uuid4())

    def path(self, document_id: UUID) -> Path:
        return self.root / "papers" / (str(document_id) + ".pdf")

    def publish(self, staged: Path, document_id: UUID) -> Path:
        target = self.path(document_id)
        # Same-volume atomic rename; fsync staged bytes before metadata commit.
        os.replace(staged, target)
        directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return target
