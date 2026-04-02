from typing import Optional
from celery.result import AsyncResult
from core.celery_app import celery
from services.parser.storage import setup_user_directories
from services.parser.tasks import parse_file_task, parse_github_task
from services.parser.validation import ensure_safe_identifier, extract_github_username


class ParserService:
    """Core parser logic, separate from FastAPI routes."""

    @staticmethod
    def queue_tasks(user_id: str, file_id: Optional[str] = None, github_url: Optional[str] = None) -> dict:
        # Validate identifiers
        user_id = ensure_safe_identifier(user_id, "user_id")
        file_id_safe = ensure_safe_identifier(file_id, "file_id") if file_id else None
        github_username = extract_github_username(str(github_url)) if github_url else None

        dirs = setup_user_directories(user_id)
        files_dir = dirs["files"]

        # Check file exists
        if file_id_safe:
            pdf_path = files_dir / f"{file_id_safe}.pdf"
            if not pdf_path.exists():
                raise FileNotFoundError(f"File {file_id_safe}.pdf not found")

        # Queue tasks
        task_ids = {"github_task_id": None, "file_task_id": None}
        if github_username:
            task_ids["github_task_id"] = parse_github_task.delay(user_id, github_username).id
        if file_id_safe:
            task_ids["file_task_id"] = parse_file_task.delay(user_id, file_id_safe).id

        return {
            "status": "queued",
            "user_id": user_id,
            "file_id": file_id_safe,
            "github_url": str(github_url) if github_url else None,
            "github_username": github_username,
            **task_ids,
        }

    @staticmethod
    def get_task_status(task_id: str) -> dict:
        task_result = AsyncResult(task_id, app=celery)
        payload = {"task_id": task_id, "status": task_result.status}

        if task_result.successful():
            payload["result"] = task_result.result
        elif task_result.failed():
            payload["error"] = str(task_result.result)

        return payload
