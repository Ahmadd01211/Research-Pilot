"""Process one durable, bounded batch from a versioned document index."""

from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.modules.documents.indexing import run_index
from app.workers.celery_app import celery_app


def index_document(index_id: str) -> None:
    settings = get_settings()
    if not settings.embedding_enabled:
        return
    engine = create_engine(
        settings.database_url.get_secret_value(), pool_pre_ping=True, hide_parameters=True
    )
    try:
        run_index(sessionmaker(engine, expire_on_commit=False), settings, UUID(index_id))
    finally:
        engine.dispose()


celery_app.task(name="researchpilot.embeddings.index", ignore_result=True)(index_document)
