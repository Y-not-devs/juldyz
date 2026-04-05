import asyncio
import os

import uvicorn
from fastapi import APIRouter, FastAPI
from fastapi.responses import RedirectResponse

from core.config import SERVICES

api = FastAPI(title=f"{SERVICES['dashboard-service']['prefix']} API")
app = api
router = APIRouter(tags=["dashboard-service"])

STREAMLIT_DASHBOARD_URL = os.getenv("STREAMLIT_DASHBOARD_URL", "http://localhost:8501")


@router.get("/")
async def dashboard_root():
    return RedirectResponse(url=STREAMLIT_DASHBOARD_URL, status_code=307)


@router.get("/health")
async def health():
    return {"status": "ok", "service": "dashboard"}


api.include_router(router)


async def main():
    cfg = SERVICES["dashboard-service"]
    config = uvicorn.Config(
        api,
        host=cfg["url"].replace("http://", "").replace("https://", ""),
        port=cfg["port"],
        log_level=cfg["log_level"],
    )
    server = uvicorn.Server(config)
    print(f"[DASHBOARD] starting api on :{cfg['port']}")
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
