from core.logger import setup_logging
setup_logging("scoring")

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="scoring-service")



@app.get("/health")
def health():
    return {"status": "ok", "service": "scoring"}