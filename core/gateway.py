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

from core.clients import BotClient, FormClient, ParserClient, ScoringClient
from core.config import GATEWAY_HOST, GATEWAY_PORT, LOG_LEVEL, SERVICES
from core.events import SystemEvent
from core.logger import setup_logging
from core.orchestrator import Orchestrator, PipelineRegistry
from core.pipelines import CandidatePipeline

setup_logging("gateway")

ROOT = Path(__file__).parent.parent
_processes: dict[str, subprocess.Popen] = {}
INTERNAL_FASTAPI_SERVICES = {
    "form-service",
    "bot-service",
    "scoring-service",
    "parser-service",
    "llm-service",
}


def _service_app_key(service_name: str) -> str:
    module_path = SERVICES[service_name]["script"].replace("\\", "/").replace("/", ".")
    module_name = module_path.removesuffix(".py")
    return f"{module_name}:api"


def start_services() -> None:
    for name, cfg in SERVICES.items():
        if name not in INTERNAL_FASTAPI_SERVICES:
            continue
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

form_client = FormClient()
parser_client = ParserClient()
scoring_client = ScoringClient()
bot_client = BotClient()
candidate_pipeline = CandidatePipeline(
    parser_client=parser_client,
    scoring_client=scoring_client,
    bot_client=bot_client,
)
orchestrator = Orchestrator(
    pipelines=PipelineRegistry(candidate=candidate_pipeline),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_services()
    await asyncio.sleep(1.5)
    print(f"[GATEWAY] ready - services: {list(_processes.keys())}")
    yield
    stop_services()


app = FastAPI(title="juldyz-gateway", lifespan=lifespan)


async def _proxy(service: str, path: str, request: Request) -> JSONResponse:
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


@app.post("/form-submit")
async def form_submit(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"status": "error", "detail": "Invalid JSON payload"}, status_code=400)

    try:
        form_result = await form_client.submit_form(payload)
    except RuntimeError as exc:
        return JSONResponse({"status": "error", "detail": str(exc)}, status_code=502)

    if form_result.get("status") != "ok":
        return JSONResponse(form_result, status_code=400)

    event = SystemEvent(
        type="form_completed",
        payload={
            "candidate_id": form_result.get("candidate_id"),
            "form_payload": {
                **payload.get("data", {}),
                "tg_id": payload.get("tg_id"),
            },
        },
    )
    try:
        workflow_result = await orchestrator.handle_event(event)
    except Exception as exc:
        return JSONResponse(
            {
                "status": "partial_success",
                "form": form_result,
                "workflow_error": str(exc),
            },
            status_code=202,
        )

    return {
        "status": "ok",
        "form": form_result,
        "workflow": workflow_result,
    }


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
