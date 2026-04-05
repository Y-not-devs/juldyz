from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from core.logger import setup_logging
from core.config import SERVICES
import subprocess
import sys

import uvicorn
setup_logging("dashboard")

def run_dashboard():
    port = SERVICES["dashboard-service"]["page_port"]
    process = subprocess.Popen([
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "services/dashboard/service.py",
        f"--server.port={port}",
        "--server.headless=true",
    ])
    return process


def stop_dashboard(process):
    if process and process.poll() is None:
        process.terminate()

api = FastAPI(title=f"{SERVICES['dashboard-service']['prefix']} API")
router = APIRouter(tags=["dashboard-service"])

@router.post("/dashboard")
async def notify():
    return {"status": "ok"}

@router.get("/health")
async def health():
    return {"status": "ok"}

@asynccontextmanager
async def lifespan(app: FastAPI):
    process = run_dashboard()
    app.state.dashboard_process = process
    yield
    stop_dashboard(process)

api.include_router(router)
run_dashboard()
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