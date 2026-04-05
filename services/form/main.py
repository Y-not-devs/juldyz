import asyncio
import uvicorn
from fastapi import FastAPI, APIRouter
from fastapi.responses import JSONResponse

from core.config import SERVICES
from core.logger import setup_logging
from core.orchestrator import Orchestrator
from services.form.service import FormService
from services.form.schemas.payload import FormSubmitRequest, FormSubmitResponse

setup_logging(SERVICES['form-service']['prefix'])

api = FastAPI(title=f"{SERVICES['form-service']['prefix']} API")
router = APIRouter(tags=["form-service"])
orchestrator = Orchestrator()
# --- Routes ---
@router.post("/form-submit", response_model=FormSubmitResponse)
async def form_submit(payload: FormSubmitRequest):
    tg_id = payload.tg_id.strip()
    if not tg_id:
        return JSONResponse({"status": "error", "detail": "no tg_id"}, status_code=400)

    candidate = FormService.get_candidate(tg_id)
    if not candidate:
        return JSONResponse(
            {"status": "error", "detail": "candidate not found, start bot first"},
            status_code=404
        )

    raw = payload.model_dump()
    candidate_id = candidate["id"]
    FormService.save_response(candidate_id, raw)
    await orchestrator.handle_form_submission(raw)
    print(f"[FORM] saved candidate_id={candidate_id} tg_id={tg_id}")
    return {"status": "ok", "candidate_id": str(candidate_id)}

@router.get("/health")
async def health():
    return {"status": "ok", "service": "form"}

# Include router in API
api.include_router(router)

# --- Entry point ---
async def main():
    cfg = SERVICES['form-service']
    config = uvicorn.Config(
        api,
        host=cfg['url'],
        port=cfg['port'],
        log_level=cfg['log_level']
    )
    server = uvicorn.Server(config)
    print(f"[FORM] starting api on :{cfg['port']}")
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())