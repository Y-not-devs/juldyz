from core.logger import setup_logging
setup_logging("parser")

from typing import Optional
from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl

from services.parser.celery_app import celery_app
from services.parser.storage import setup_user_directories
from services.parser.tasks import parse_file_task, parse_github_task
from services.parser.validation import (
    ensure_safe_identifier,
    extract_github_username,
)

app = FastAPI()


class ParseRequest(BaseModel):
    user_id: str
    file_id: Optional[str] = None
    github_url: Optional[HttpUrl] = None


@app.post("/parse")
async def start_parsing(request: ParseRequest):
    if not request.file_id and not request.github_url:
        raise HTTPException(
            status_code=422,
            detail="Provide file_id and/or github_url",
        )

    try:
        user_id = ensure_safe_identifier(request.user_id, "user_id")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    file_id: Optional[str] = None
    if request.file_id:
        try:
            file_id = ensure_safe_identifier(request.file_id, "file_id")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    github_username: Optional[str] = None
    if request.github_url:
        try:
            github_username = extract_github_username(str(request.github_url))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    dirs = setup_user_directories(user_id)
    files_dir = dirs["files"]

    task_ids: dict[str, Optional[str]] = {
        "github_task_id": None,
        "file_task_id": None,
    }

    if file_id:
        pdf_path = files_dir / f"{file_id}.pdf"
        if not pdf_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"File {file_id}.pdf not found in data/files",
            )

    if github_username:
        github_async_result = parse_github_task.delay(
            user_id,
            github_username,
        )
        task_ids["github_task_id"] = github_async_result.id

    if file_id:
        file_async_result = parse_file_task.delay(user_id, file_id)
        task_ids["file_task_id"] = file_async_result.id

    return {
        "status": "queued",
        "user_id": user_id,
        "file_id": file_id,
        "github_url": str(request.github_url) if request.github_url else None,
        "github_username": github_username,
        **task_ids,
    }


@app.get("/parse/tasks/{task_id}")
async def get_task_status(task_id: str):
    task_result = AsyncResult(task_id, app=celery_app)
    payload = {
        "task_id": task_id,
        "status": task_result.status,
    }

    if task_result.successful():
        payload["result"] = task_result.result
    elif task_result.failed():
        payload["error"] = str(task_result.result)

    return payload


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8003)
