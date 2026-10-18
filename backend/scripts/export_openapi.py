"""Generate a deterministic public contract without opening a database connection."""
import json
import sys
from pathlib import Path

from app.core.config import Settings
from app.main import create_app

settings = Settings(database_url="postgresql+psycopg://schema@localhost/schema", redis_url="redis://localhost:6379/0", environment="test")
Path(sys.argv[1]).write_text(json.dumps(create_app(settings).openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
