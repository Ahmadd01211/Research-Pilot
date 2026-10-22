"""Run separately from web/worker. Multiple instances are safe via SKIP LOCKED."""

import logging
import signal
import time

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.modules.documents.indexing import dispatch_once as dispatch_embeddings
from app.modules.documents.processing import dispatch_once
from app.workers.celery_app import celery_app

logger = logging.getLogger("researchpilot.dispatcher")
stopping = False


def stop(_signum: int, _frame: object) -> None:
    global stopping
    stopping = True


def publish(document_id: str) -> None:
    celery_app.send_task(
        "researchpilot.documents.extract", args=[document_id], queue="documents", retry=False
    )


def publish_embedding(index_id: str) -> None:
    celery_app.send_task(
        "researchpilot.embeddings.index", args=[index_id], queue="embeddings", retry=False
    )


def main() -> None:
    settings = get_settings()
    engine = create_engine(
        settings.database_url.get_secret_value(), pool_pre_ping=True, hide_parameters=True
    )
    factory = sessionmaker(engine, expire_on_commit=False)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        while not stopping:
            try:
                dispatch_once(factory, publish)
                if settings.embedding_enabled:
                    dispatch_embeddings(factory, publish_embedding)
                # Operational heartbeat, no source text or user identifiers.
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            "INSERT INTO processing_heartbeat (id,ticked_at) VALUES (1,CURRENT_TIMESTAMP) ON CONFLICT (id) DO UPDATE SET ticked_at=CURRENT_TIMESTAMP"
                        )
                    )
            except Exception as error:
                logger.warning("dispatch_unavailable category=%s", type(error).__name__)
            time.sleep(3)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
