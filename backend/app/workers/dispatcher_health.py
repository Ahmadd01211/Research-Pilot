from sqlalchemy import create_engine, text

from app.core.config import get_settings

engine = create_engine(get_settings().database_url.get_secret_value())
try:
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT ticked_at > CURRENT_TIMESTAMP - INTERVAL '45 seconds' FROM processing_heartbeat WHERE id=1"
                )
            )
            is True
        )
finally:
    engine.dispose()
