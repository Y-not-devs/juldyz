import sys
import time
import signal
import subprocess
import asyncio
from pathlib import Path

from core.logging import setup_logging
setup_logging("gateway")

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.hub import hub
from core.db import db

ROOT = Path(__file__).parent.parent

SERVICES = {
    "form":    {"script": "services/form/main.py",    "port": 8001},
    "bot":     {"script": "services/bot/main.py",     "port": 8002},
    "scoring": {"script": "services/scoring/main.py", "port": 8003},
    "parser":  {"script": "services/parser/main.py",  "port": 8004},
}

_processes: dict[str, subprocess.Popen] = {}

app = FastAPI(title="juldyz-gateway")


# --- lifecycle ---

def start_services():
    for name, cfg in SERVICES.items():
        script = ROOT / cfg["script"]
        if not script.exists():
            print(f"[GATEWAY] skip {name} — {script} not found")
            continue
        print(f"[GATEWAY] starting {name} on :{cfg['port']}")
        proc = subprocess.Popen(
            [sys.executable, str(script)],
            cwd=str(ROOT)
        )
        _processes[name] = proc
        time.sleep(0.5)


def stop_services():
    for name, proc in _processes.items():
        print(f"[GATEWAY] stopping {name}")
        try:
            proc.terminate()
            hub.unregister(name)
        except Exception as e:
            print(f"[GATEWAY] error stopping {name}: {e}")


def handle_exit(sig, frame):
    stop_services()
    sys.exit(0)


signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)


@app.on_event("startup")
async def startup():
    db._init()
    print("[GATEWAY] db initialized")
    start_services()
    await asyncio.sleep(2)
    print(f"[GATEWAY] ready — services: {list(_processes.keys())}")


# --- health ---

@app.get("/health")
async def health():
    registered = hub.all()
    results = {}
    async with httpx.AsyncClient() as client:
        for name, info in registered.items():
            url = f"http://localhost:{info['port']}/health"
            try:
                r = await client.get(url, timeout=2)
                results[name] = r.json()
            except Exception:
                results[name] = {"status": "unreachable"}
    return {"gateway": "ok", "services": results}


@app.get("/services")
def services():
    return hub.all()


# --- proxy ---

async def _proxy(service: str, path: str, request: Request):
    url = hub.locate(service)
    if not url:
        return JSONResponse(
            {"error": f"service '{service}' not registered in hub"},
            status_code=503
        )
    body = await request.body()
    async with httpx.AsyncClient() as client:
        r = await client.request(
            method=request.method,
            url=f"{url}{path}",
            content=body,
            headers={"Content-Type": request.headers.get("Content-Type", "application/json")},
            timeout=10
        )
    return JSONResponse(status_code=r.status_code, content=r.json())


# --- routes ---

@app.post("/form-submit")
async def route_form(request: Request):
    return await _proxy("form", "/form-submit", request)

@app.post("/notify")
async def route_notify(request: Request):
    return await _proxy("bot", "/notify", request)

@app.post("/score")
async def route_score(request: Request):
    return await _proxy("scoring", "/score", request)

@app.post("/parse")
async def route_parse(request: Request):
    return await _proxy("parser", "/parse", request)

@app.get("/candidates")
async def route_candidates(request: Request):
    return await _proxy("scoring", "/candidates", request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)