from fastapi import FastAPI, APIRouter
from core.logger import setup_logging
from core.config import SERVICES

setup_logging("dashboard")

api = FastAPI(title="dashboard-service")
router = APIRouter()


@app.on_event("startup")
def startup():
    run_dashboard()
    
@router.get("/health")
async def health():
    return {"status": "ok"}

api.include_router(router)