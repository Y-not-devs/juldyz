import asyncio
import uvicorn
from fastapi import FastAPI, APIRouter
from celery.result import AsyncResult

from core.logger import setup_logging
from core.config import SERVICES
from core.celery_app import celery

from services.llm.tasks import generate_text_task

setup_logging(SERVICES['llm-service']['prefix'])

api = FastAPI(title=f"{SERVICES['llm-service']['prefix']} API")
router = APIRouter(tags=["llm-service"])

@router.get("/health")
async def health():
    return {"status": "ok", "service": "llm"}

@router.post("/generate")
async def generate_text(prompt: dict):
    """
    Queue a task to generate text using the LLM service.
    :param prompt: A dictionary containing the instruction and input text.
    :return: Task ID for the queued task.
    """
    try:
        instruction = prompt.get("instruction", "")
        text = prompt.get("text", "")
        if not instruction or not text:
            return {"error": "Both 'instruction' and 'text' are required"}

        # Queue the task
        task = generate_text_task.delay(instruction, text)
        return {"task_id": task.id}
    except Exception as e:
        return {"error": str(e)}

@router.get("/result/tasks/{task_id}")
async def check_task_status(task_id: str):
    """
    Check the status of a Celery task.
    :param task_id: The ID of the task to check.
    :return: The status and result of the task.
    """
    try:
        task_result = AsyncResult(task_id, app=celery)
        status = task_result.status
        result = task_result.result if task_result.successful() else None
        return {"task_id": task_id, "status": status, "result": result}
    except Exception as e:
        return {"error": str(e)}

api.include_router(router)

# --- Entry point ---
async def main():
    cfg = SERVICES['llm-service']
    config = uvicorn.Config(
        api,
        host=cfg['url'],
        port=cfg['port'],
        log_level=cfg['log_level']
    )
    server = uvicorn.Server(config)

    print(f"[LLM] starting polling + api on :{cfg['port']}")
    await asyncio.gather(
        server.serve()
    )


if __name__ == "__main__":
    asyncio.run(main())
