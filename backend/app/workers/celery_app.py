from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery(
    "researchpilot_greenfield",
    broker=settings.redis_url.get_secret_value(),
    include=["app.workers.document_tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=120,
    task_time_limit=150,
    broker_transport_options={
        "visibility_timeout": 300,
        "socket_connect_timeout": 3,
        "socket_timeout": 3,
    },
    broker_connection_timeout=3,
    broker_pool_limit=2,
    task_publish_retry=False,
    task_default_queue="documents",
    task_routes={
        "researchpilot.documents.*": {"queue": "documents"},
        "researchpilot.embeddings.*": {"queue": "embeddings"},
        "researchpilot.analysis.*": {"queue": "analysis"},
        "researchpilot.exports.*": {"queue": "exports"},
    },
)
# PostgreSQL job rows provide durable dispatch intent and processing state.
