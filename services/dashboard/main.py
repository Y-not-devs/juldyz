from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from core.logger import setup_logging
from core.config import SERVICES
import subprocess
import sys

setup_logging("dashboard")

def run_dashboard():
    subprocess.Popen([
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "services/dashboard/app.py",
        "--server.port=8501",
        "--server.headless=true",
    ])


def stop_dashboard(process):
    if process and process.poll() is None:
        process.terminate()

api = FastAPI(title="dashboard-service")
router = APIRouter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    process = run_dashboard()
    app.state.dashboard_process = process

    yield

    # shutdown
    stop_dashboard(app.state.dashboard_process)
@router.get("/health")
async def health():
    return {"status": "ok"}

api.include_router(router)