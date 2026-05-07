"""Celery application configuration."""
from celery import Celery
from app.config import settings

VISIBILITY_TIMEOUT_SECONDS = 6 * 60 * 60

celery_app = Celery(
    "ai_short_film",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.llm_tasks",
        "app.tasks.image_tasks",
        "app.tasks.video_tasks",
        "app.tasks.merge_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    broker_transport_options={"visibility_timeout": VISIBILITY_TIMEOUT_SECONDS},
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.llm.*": {"queue": "llm"},
        "app.tasks.image.*": {"queue": "image"},
        "app.tasks.video.*": {"queue": "video"},
        "app.tasks.merge.*": {"queue": "merge"},
    },
)
