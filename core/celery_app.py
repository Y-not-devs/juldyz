from celery import Celery
from core.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

celery = Celery(
    "core",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "services.parser.tasks",
        "services.parser.tasks_video",
        "services.llm.tasks",
    ],
)
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    timezone="UTC",
    enable_utc=True,
)

# queues per service
celery.conf.task_routes = {
    "parser.*": {"queue": "parser"},
    "llm.*": {"queue": "llm"},
}
