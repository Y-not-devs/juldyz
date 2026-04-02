from functools import lru_cache
from typing import Any

from core.celery_app import celery
from core.config import SERVICES
from core.db import db


@lru_cache(maxsize=1)
def get_llm_service() -> Any:
    from services.llm.service import LLM_Service

    cfg = SERVICES["llm-service"]
    return LLM_Service(
        db=db,
        model_path=cfg["model_path"],
        hf_model_id=cfg["hf_model_id"],
        hf_token=cfg["hf_token"],
        mode=cfg["mode"],
    )


@celery.task(name="llm.generate_text")
def generate_text_task(instruction: str, text: str) -> str:
    llm_service = get_llm_service()
    return llm_service.generate_response(f"{instruction}: {text}")
