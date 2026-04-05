from __future__ import annotations

import asyncio
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import APIRouter, FastAPI

from core.config import SERVICES
from core.logger import setup_logging

setup_logging("dashboard")

SERVICE_FILE = Path(__file__).resolve().parent / "service.py"


def run_dashboard() -> subprocess.Popen:
    port = SERVICES["dashboard-service"]["page_port"]
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(SERVICE_FILE),
            f"--server.port={port}",
            "--server.headless=true",
        ]
    )
    return process


def stop_dashboard(process: subprocess.Popen | None) -> None:
    if process and process.poll() is None:
        process.terminate()


@asynccontextmanager
async def lifespan(app: FastAPI):
    process = run_dashboard()
    app.state.dashboard_process = process
    yield
    stop_dashboard(process)


api = FastAPI(title=f"{SERVICES['dashboard-service']['prefix']} API", lifespan=lifespan)
router = APIRouter(tags=["dashboard-service"])


@router.post("/dashboard")
async def notify():
    return {"status": "ok"}


@router.get("/health")
async def health():
    return {"status": "ok", "service": "dashboard"}


api.include_router(router)


async def main():
    cfg = SERVICES["dashboard-service"]
    host = cfg["url"].replace("http://", "").replace("https://", "")
    config = uvicorn.Config(
        api,
        host=host,
        port=cfg["port"],
        log_level=cfg["log_level"],
    )
    server = uvicorn.Server(config)
    print(f"[DASHBOARD] starting api on :{cfg['port']}")
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
