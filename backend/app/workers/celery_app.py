from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery("researchpilot_greenfield", broker=settings.redis_url.get_secret_value())
celery_app.conf.update(
    task_serializer="json", accept_content=["json"], result_serializer="json",
    task_acks_late=True, task_reject_on_worker_lost=True, worker_prefetch_multiplier=1,
    task_soft_time_limit=120, task_time_limit=150,
    broker_transport_options={"visibility_timeout": 300},
    task_default_queue="documents",
    task_routes={"researchpilot.documents.*": {"queue": "documents"},
                 "researchpilot.embeddings.*": {"queue": "embeddings"},
                 "researchpilot.analysis.*": {"queue": "analysis"},
                 "researchpilot.exports.*": {"queue": "exports"}},
)
# No fake processing tasks. Durable job/outbox dispatch starts with the library slice.
