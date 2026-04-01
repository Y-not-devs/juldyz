import asyncio
import uvicorn
from fastapi import FastAPI, APIRouter

from core.logger import setup_logging
from core.config import SERVICES
from core.db import db

from services.scoring.service import ScoringService
setup_logging(SERVICES['scoring-service']['prefix'])

api = FastAPI(title=f"{SERVICES['scoring-service']['prefix']} API")
router = APIRouter(tags=["scoring-service"])

@router.get("/health")
async def health():
    return {"status": "ok", "service": "scoring"}

api.include_router(router)

# --- Entry point ---
async def main():
    cfg = SERVICES['scoring-service']
    config = uvicorn.Config(
        api,
        host=cfg['url'],
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