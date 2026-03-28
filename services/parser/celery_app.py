import os

from celery import Celery

DEFAULT_BROKER_URL = "redis://localhost:6379/0"

broker_url = os.getenv("PARSER_CELERY_BROKER_URL", DEFAULT_BROKER_URL)
result_backend = os.getenv("PARSER_CELERY_RESULT_BACKEND", broker_url)

celery_app = Celery(
    "parser",
    broker=broker_url,
    backend=result_backend,
    include=["services.parser.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    timezone="UTC",
    enable_utc=True,
)
