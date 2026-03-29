import sys
import time
import signal
import subprocess
import asyncio
import os
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

# --- logging ---
from logger import setup_logging
setup_logging("gateway")

# --- path setup ---
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# --- SERVICES ---
SERVICES = {
    "form-service":    {"script": "services/form/main.py",    "port": 8001},
    "bot-service":     {"script": "services/bot/main.py",     "port": 8002},
    "scoring-service": {"script": "services/scoring/main.py", "port": 8003},
    "parser-service":  {"script": "services/parser/main.py",  "port": 8004},
}

_processes: dict[str, subprocess.Popen] = {}

# =====================================================
# SERVICE CONTROL
# =====================================================
def start_services():
    for name, cfg in SERVICES.items():
        script = ROOT / cfg["script"]
        if not script.exists():
            print(f"[GATEWAY] skip {name} — {script} not found")
            continue

        print(f"[GATEWAY] starting {name} on :{cfg['port']}")
        proc = subprocess.Popen(
            [sys.executable, str(script)],
            cwd=str(ROOT),
            env={**os.environ, "PYTHONPATH": str(ROOT)},
        )
        _processes[name] = proc
        time.sleep(0.5)

def stop_services():
    for name, proc in _processes.items():
        print(f"[GATEWAY] stopping {name}")
        try:
            proc.terminate()
        except Exception as e:
            print(f"[GATEWAY] error stopping {name}: {e}")

def handle_exit(sig, frame):
    stop_services()
    sys.exit(0)

signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)

# =====================================================
# FASTAPI LIFESPAN
# =====================================================
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_services()
    await asyncio.sleep(2)
    print(f"[GATEWAY] ready — services: {list(_processes.keys())}")
    yield
    stop_services()

# =====================================================
# APP INIT
# =====================================================
app = FastAPI(title="juldyz-gateway", lifespan=lifespan)

# =====================================================
# INTERNAL PROXY
# =====================================================
async def _proxy(service: str, path: str, request: Request):
    cfg = SERVICES.get(service)
    if not cfg:
        return JSONResponse({"error": f"unknown service '{service}'"}, status_code=404)

    url = f"http://localhost:{cfg['port']}/{path}"
    body = await request.body()

    try:
        async with httpx.AsyncClient() as client:
            r = await client.request(
                method=request.method,
                url=url,
                content=body,
                headers={"Content-Type": request.headers.get("Content-Type", "application/json")},
                timeout=10
            )
    except httpx.ConnectError:
        return JSONResponse(
            {"status": "error", "detail": f"{service} is not reachable"},
            status_code=502
        )
    except httpx.TimeoutException:
        return JSONResponse(
            {"status": "error", "detail": f"{service} timed out"},
            status_code=504
        )

    try:
        content = r.json()
    except Exception:
        content = {
            "status": "error",
            "detail": "upstream returned non-JSON",
            "upstream_status": r.status_code,
            "body": r.text[:200]
        }
    return JSONResponse(status_code=r.status_code, content=content)

# =====================================================
# DYNAMIC API ROUTE
# =====================================================
@app.api_route(
    "/api/{service}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"]
)
async def api_proxy(service: str, path: str, request: Request):
    return await _proxy(service, path, request)

# =====================================================
# HEALTH CHECK
# =====================================================
@app.get("/health")
async def health():
    return {"gateway": "ok", "services": list(SERVICES.keys())}

# =====================================================
# ENTRYPOINT
# =====================================================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")