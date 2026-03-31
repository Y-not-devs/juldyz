from core.logger import setup_logging
from core.config import SERVICES
setup_logging(SERVICES["scoring-service"]["prefix"])

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title=f"{SERVICES['scoring-service']['prefix']} API")



@app.get("/health")
def health():
    return {"status": "ok", "service": "scoring"}