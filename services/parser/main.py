from typing import Optional

from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl

from services.parser.celery_app import celery_app
from services.parser.storage import setup_user_directories
from services.parser.tasks import parse_file_task, parse_github_task

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

    dirs = setup_user_directories(request.user_id)
    files_dir = dirs["files"]

    task_ids: dict[str, Optional[str]] = {
        "github_task_id": None,
        "file_task_id": None,
    }

    if request.file_id:
        pdf_path = files_dir / f"{request.file_id}.pdf"
        if not pdf_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"File {request.file_id}.pdf not found in data/files",
            )

    if request.github_url:
        github_async_result = parse_github_task.delay(
            request.user_id,
            str(request.github_url),
        )
        task_ids["github_task_id"] = github_async_result.id

    if request.file_id:
        file_async_result = parse_file_task.delay(request.user_id, request.file_id)
        task_ids["file_task_id"] = file_async_result.id

    return {
        "status": "queued",
        "user_id": request.user_id,
        "file_id": request.file_id,
        "github_url": str(request.github_url) if request.github_url else None,
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
