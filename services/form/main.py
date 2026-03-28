import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.db import db
from core.config import BOT_SERVICE_URL

app = FastAPI(title="form-service")


@app.post("/form-submit")
async def form_submit(request: Request):
    payload = await request.json()

    tg_id = str(payload.get("tg_id", "")).strip()
    if not tg_id:
        return JSONResponse({"status": "error", "detail": "no tg_id"}, status_code=400)

    candidate = db.get_candidate_by_tg(tg_id)
    if not candidate:
        return JSONResponse({"status": "error", "detail": "candidate not found, start bot first"}, status_code=404)

    candidate_id = candidate["id"]
    db.set_form_data(candidate_id, payload)

    # notify bot
    try:
        async with httpx.AsyncClient() as client:
            await client.post(f"{BOT_SERVICE_URL}/notify", json={
                "tg_id": tg_id,
                "candidate_id": candidate_id
            }, timeout=5)
    except Exception as e:
        print(f"[FORM] bot notify failed: {e}")

    print(f"[FORM] candidate_id={candidate_id} tg_id={tg_id} form saved")
    return JSONResponse({"status": "ok", "candidate_id": candidate_id})


@app.get("/health")
def health():
    return {"status": "ok", "service": "form"}