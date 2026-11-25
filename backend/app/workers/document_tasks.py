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


# Parsing may use PARSER_WALL_SECONDS (100s); publication (page rows, chunk inserts,
# index queueing) then needs a real margin before the soft limit, and the hard limit
# must stay below the job lease (240s) so a live worker is never treated as abandoned.
EXTRACT_SOFT_SECONDS = 160
EXTRACT_HARD_SECONDS = 190
celery_app.task(
    name="researchpilot.documents.extract",
    ignore_result=True,
    soft_time_limit=EXTRACT_SOFT_SECONDS,
    time_limit=EXTRACT_HARD_SECONDS,
)(extract_document)
