from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.modules.documents.processing import run_document
from app.modules.documents.storage import LocalStorage
from app.workers.celery_app import celery_app


def extract_document(document_id: str) -> None:
    settings = get_settings()
    engine = create_engine(
        settings.database_url.get_secret_value(), pool_pre_ping=True, hide_parameters=True
    )
    try:
        run_document(
            sessionmaker(engine, expire_on_commit=False),
            LocalStorage(settings.storage_root),
            UUID(document_id),
            settings,
        )
    finally:
        engine.dispose()


celery_app.task(name="researchpilot.documents.extract", ignore_result=True)(extract_document)
