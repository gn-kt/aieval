import os

from celery import Celery

from config import REDIS_URL

_IS_TESTING = os.getenv("TESTING", "").lower() in ("1", "true", "yes")

celery_app = Celery(
    "rag_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks"],
)

if _IS_TESTING:
    celery_app.conf.broker_url = "memory://"
    celery_app.conf.result_backend = "cache+memory://"
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_store_eager_result = True
    celery_app.conf.task_serializer = "json"
    celery_app.conf.result_serializer = "json"
    celery_app.conf.accept_content = ["json"]
    celery_app.conf.timezone = "UTC"
    celery_app.conf.enable_utc = True
else:
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_soft_time_limit=30,
        task_time_limit=60,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
    )
