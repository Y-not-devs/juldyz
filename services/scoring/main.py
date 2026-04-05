import asyncio
import uvicorn
from fastapi import FastAPI, APIRouter

from core.logger import setup_logging
from core.config import SERVICES

from services.scoring.service import ScoringService
setup_logging(SERVICES['scoring-service']['prefix'])

api = FastAPI(title=f"{SERVICES['scoring-service']['prefix']} API")
router = APIRouter(tags=["scoring-service"])

@router.get("/health")
async def health():
    return {"status": "ok", "service": "scoring"}

scoring_service = ScoringService()

@router.post("/evaluate")
async def evaluate(candidate_data: dict):
    """
    Эндпоинт для оценки кандидата. 
    Принимает JSON с данными формы, гитхаба и т.д.
    """
    try:
        result = await scoring_service.evaluate_candidate(candidate_data)
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

api.include_router(router)

# --- Entry point ---
async def main():
    cfg = SERVICES['scoring-service']
    config = uvicorn.Config(
        api,
        host="127.0.0.1",
        port=cfg['port'],
        log_level=cfg['log_level']
    )
    server = uvicorn.Server(config)

    print(f"[BOT] starting polling + api on :{cfg['port']}")
    await asyncio.gather(
        server.serve()
    )


if __name__ == "__main__":
    asyncio.run(main())