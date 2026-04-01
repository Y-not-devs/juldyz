import sys
import time
import signal
import subprocess
import asyncio
import os
from pathlib import Path
import importlib.util

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

# --- logging ---
from core.logger import setup_logging
from core.config import SERVICES, GATEWAY_HOST, GATEWAY_PORT, LOG_LEVEL

from services.bot.main import router as bot_router

setup_logging("gateway")

# --- path setup ---
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

_processes: dict[str, subprocess.Popen] = {}

def start_services():
    for name, cfg in SERVICES.items():
        # Try to import the FastAPI app from main.py
        main_path = ROOT / cfg["script"]
        try:
            # Expect main.py to expose `api` if structured new way
            import importlib.util
            spec = importlib.util.spec_from_file_location(name, str(main_path))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            app = getattr(mod, "api", None)
            if app:
                print(f"[GATEWAY] {name} exposes FastAPI app — skipping subprocess")
                continue  # skip starting subprocess; gateway can directly proxy
        except Exception:
            pass  # fallback to old subprocess method

        if not main_path.exists():
            print(f"[GATEWAY] skip {name} — {main_path} not found")
            continue

        print(f"[GATEWAY] starting {name} on :{cfg['port']} with log_level={cfg['log_level']}")
        proc = subprocess.Popen(
            [sys.executable, str(main_path)],
            cwd=str(ROOT),
            env={
                **os.environ,
                "PYTHONPATH": str(ROOT),
                "SERVICE_NAME": name,
                "SERVICE_PORT": str(cfg["port"]),
                "SERVICE_LOG_LEVEL": cfg["log_level"],
            },
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

app.include_router(bot_router, prefix=f"/{SERVICES['bot-service']['prefix']}")

# =====================================================
# INTERNAL PROXY
# =====================================================
async def _proxy(service: str, path: str, request: Request):
    cfg = SERVICES.get(service)
    if not cfg:
        return JSONResponse({"error": f"unknown service '{service}'"}, status_code=404)

    url = f"{cfg['url']}:{cfg['port']}/{path}"
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
    status = []
    for name, cfg in SERVICES.items():
        main_path = ROOT / cfg["script"]
        try:
            spec = importlib.util.spec_from_file_location(name, str(main_path))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            app = getattr(mod, "api", None)
            has_app = bool(app)
        except Exception:
            has_app = False

        status.append({
            "name": name,
            "url": f"{cfg['url']}:{cfg['port']}",
            "log_level": cfg["log_level"],
            "fastapi_app": has_app
        })
    return {"gateway": "ok", "services": status}

# =====================================================
# ENTRYPOINT
# =====================================================
if __name__ == "__main__":
    uvicorn.run(app, host=GATEWAY_HOST, port=GATEWAY_PORT, log_level=LOG_LEVEL)