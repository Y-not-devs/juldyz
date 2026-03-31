import asyncio
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

from core.db import db
from core.config import SERVICES
from core.logger import setup_logging

setup_logging("form")

api = FastAPI(title=f"{SERVICES['form-service']['prefix']} API")

@api.post("/form-submit")
async def form_submit(request: Request):
    payload = await request.json()

    # log full payload
    print(f"[FORM] received payload: {payload}")

    tg_id = str(payload.get("tg_id", "")).strip()
    if not tg_id:
        return JSONResponse({"status": "error", "detail": "no tg_id"}, status_code=400)

    candidate = db.get_user_by_tg(tg_id)
    if not candidate:
        return JSONResponse(
            {"status": "error", "detail": "candidate not found, start bot first"},
            status_code=404
            )

    candidate_id = candidate["id"]
    db.save_candidate_response(candidate_id, payload)

    # notify bot
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{SERVICES['bot-service']['url']}:{SERVICES['bot-service']['port']}/notify",
                json={
                    "tg_id": tg_id,
                    "candidate_id": candidate_id
                },
                timeout=5
            )
    except Exception as e:
        print(f"[FORM] bot notify failed: {e}")

    print(f"[FORM] candidate_id={candidate_id} tg_id={tg_id} form saved")
    return JSONResponse({"status": "ok", "candidate_id": candidate_id})

@api.get("/health")
def health():
    return {"status": "ok", "service": "form"}

# --- Entry point ---
async def main():
    config = uvicorn.Config(
        api,
        host=SERVICES['form-service']['url'],
        port=SERVICES['form-service']['port'],
        log_level=SERVICES['form-service']['log_level']
    )
    server = uvicorn.Server(config)
    
    print(f"[FORM] starting api on :{SERVICES['form-service']['port']}")
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())