from celery import Celery
from core.config import REDIS_URL

celery = Celery(
    "core",
    broker=REDIS_URL,
    backend=REDIS_URL,
)
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# queues per service
celery.conf.task_routes = {
    "parser.*": {"queue": "parser"},
    "llm.*": {"queue": "llm"},
}