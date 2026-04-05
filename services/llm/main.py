import asyncio
import uvicorn
from fastapi import FastAPI, APIRouter
from celery.result import AsyncResult

from core.logger import setup_logging
from core.config import SERVICES
from core.db import db

from services.llm.service import LLM_Service
from services.llm.schemas.base import LLMGenerateRequest, LLMGenerateResponse, LLMTaskStatusResponse

setup_logging(SERVICES['llm-service']['prefix'])

api = FastAPI(title=f"{SERVICES['llm-service']['prefix']} API")
router = APIRouter(tags=["llm-service"])
llm_service = LLM_Service(
    db=db,
    # logger=setup_logging(SERVICES['llm-service']['prefix']),
    model_path=SERVICES['llm-service']['model_path'],
    hf_model_id=SERVICES['llm-service']['hf_model_id'],
    hf_token=SERVICES['llm-service']['hf_token'],
    mode=SERVICES['llm-service']['mode']
)

# @celery.task(name="llm.generate_text")
# def generate_text_task(instruction: str, text: str):
#     """
#     Celery task to generate text using the LLM service.
#     :param instruction: Instruction for the LLM.
#     :param text: Input text for the LLM.
#     :return: Generated text.
#     """
#     return llm_service.generate(f"{instruction}: {text}")

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
        prompt_text = f"{instruction}: {text}"
        response = llm_service.generate_response(prompt_text)
        return {"response": response}
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