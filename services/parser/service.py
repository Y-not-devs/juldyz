from typing import Optional
from services.parser.storage import setup_user_directories
from services.parser.tasks import parse_file_task, parse_github_task
from services.parser.tasks_video import parse_video_task
from services.parser.validation import (
    ensure_safe_identifier,
    extract_github_username,
    extract_youtube_video_id,
)


class ParserService:
    """Core parser logic, separate from FastAPI routes."""

    @staticmethod
    def _run_task_sync(task_callable, *args) -> dict:
        try:
            result = task_callable(*args)
            return {"status": "SUCCESS", "result": result}
        except Exception as exc:
            return {
                "status": "FAILURE",
                "error": str(exc),
                "error_type": type(exc).__name__,
            }

    @staticmethod
    def queue_tasks(
        user_id: str,
        file_id: Optional[str] = None,
        github_url: Optional[str] = None,
        youtube_url: Optional[str] = None,
    ) -> dict:
        # Validate identifiers
        user_id = ensure_safe_identifier(user_id, "user_id")
        file_id_safe = ensure_safe_identifier(file_id, "file_id") if file_id else None
        github_username = extract_github_username(str(github_url)) if github_url else None
        youtube_video_id = extract_youtube_video_id(str(youtube_url)) if youtube_url else None

        dirs = setup_user_directories(user_id)
        files_dir = dirs["files"]

        # Check file exists
        if file_id_safe:
            pdf_path = files_dir / f"{file_id_safe}.pdf"
            if not pdf_path.exists():
                raise FileNotFoundError(f"File {file_id_safe}.pdf not found")

        # Run tasks directly (no queue, no broker).
        results = {}
        if github_username:
            results["github_task"] = ParserService._run_task_sync(parse_github_task, user_id, github_username)
        if file_id_safe:
            results["file_task"] = ParserService._run_task_sync(parse_file_task, user_id, file_id_safe)
        if youtube_video_id:
            results["video_task"] = ParserService._run_task_sync(parse_video_task, user_id, youtube_video_id)

        success_count = sum(1 for item in results.values() if item.get("status") == "SUCCESS")
        failure_count = sum(1 for item in results.values() if item.get("status") == "FAILURE")

        return {
            "status": "completed" if failure_count == 0 else "completed_with_errors",
            "mode": "direct",
            "user_id": user_id,
            "file_id": file_id_safe,
            "github_url": str(github_url) if github_url else None,
            "github_username": github_username,
            "youtube_url": str(youtube_url) if youtube_url else None,
            "youtube_video_id": youtube_video_id,
            "github_task_id": None,
            "file_task_id": None,
            "video_task_id": None,
            "summary": {
                "requested_tasks": len(results),
                "success_count": success_count,
                "failure_count": failure_count,
            },
            "results": results,
        }
