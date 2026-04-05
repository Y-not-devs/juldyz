from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.config import GATEWAY_HOST, GATEWAY_PORT, LOG_LEVEL, SERVICES
from core.logger import setup_logging
from core.orchestrator import Orchestrator

from services import bot_router, scoring_router, llm_router, form_router, parser_router, dashboard_router


ROOT = Path(__file__).parent.parent
setup_logging("gateway")

_processes: dict[str, subprocess.Popen] = {}

def _service_app_key(service_name: str) -> str:
    module_path = SERVICES[service_name]["script"].replace("\\", "/").replace("/", ".")
    module_name = module_path.removesuffix(".py")
    return f"{module_name}:api"

def start_services() -> None:
    for name, cfg in SERVICES.items():
        app_path = _service_app_key(name)
        host = cfg["url"].replace("http://", "").replace("https://", "")
        port = cfg["port"]
        log_level = cfg["log_level"]
        print(f"[GATEWAY] starting {name} on {host}:{port}")
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                app_path,
                "--host",
                host,
                "--port",
                str(port),
                "--log-level",
                log_level,
            ],
            cwd=str(ROOT),
            env={**os.environ, "PYTHONPATH": str(ROOT)},
        )
        _processes[name] = proc
        time.sleep(0.3)


def stop_services() -> None:
    for name, proc in _processes.items():
        print(f"[GATEWAY] stopping {name}")
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def handle_exit(sig: int, frame: Any) -> None:
    stop_services()
    raise SystemExit(0)


signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)


orchestrator = Orchestrator()


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_services()
    await asyncio.sleep(1.5)
    print(f"[GATEWAY] ready - services: {list(_processes.keys())}")
    yield
    stop_services()


app = FastAPI(title="juldyz-gateway", lifespan=lifespan)

app.include_router(bot_router, prefix=f"/{SERVICES['bot-service']['prefix']}")
app.include_router(llm_router, prefix=f"/{SERVICES['llm-service']['prefix']}")
app.include_router(form_router, prefix=f"/{SERVICES['form-service']['prefix']}")
app.include_router(parser_router, prefix=f"/{SERVICES['parser-service']['prefix']}")
app.include_router(scoring_router, prefix=f"/{SERVICES['scoring-service']['prefix']}")
app.include_router(dashboard_router, prefix=f"/{SERVICES['dashboard-service']['prefix']}")

async def _proxy(service: str, path: str, request: Request):
    cfg = SERVICES.get(service)
    if not cfg:
        return JSONResponse({"error": f"unknown service '{service}'"}, status_code=404)

    url = f"{cfg['url']}:{cfg['port']}/{path}"
    body = await request.body()
    headers = {"Content-Type": request.headers.get("Content-Type", "application/json")}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.request(
                method=request.method,
                url=url,
                content=body,
                headers=headers,
            )
    except httpx.ConnectError:
        return JSONResponse({"status": "error", "detail": f"{service} is not reachable"}, status_code=502)
    except httpx.TimeoutException:
        return JSONResponse({"status": "error", "detail": f"{service} timed out"}, status_code=504)

    try:
        content = response.json()
    except Exception:
        content = {
            "status": "error",
            "detail": "upstream returned non-JSON",
            "upstream_status": response.status_code,
            "body": response.text[:200],
        }

    return JSONResponse(status_code=response.status_code, content=content)

@app.api_route("/api/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def api_proxy(service: str, path: str, request: Request):
    return await _proxy(service, path, request)

@app.get("/health")
async def health():
    status = []
    for name, cfg in SERVICES.items():
        status.append(
            {
                "name": name,
                "url": f"{cfg['url']}:{cfg['port']}",
                "log_level": cfg["log_level"],
                "running": name in _processes and _processes[name].poll() is None,
            }
        )
    return {"gateway": "ok", "services": status}

if __name__ == "__main__":
    uvicorn.run(app, host=GATEWAY_HOST, port=GATEWAY_PORT, log_level=LOG_LEVEL)
