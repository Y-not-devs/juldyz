from __future__ import annotations

import asyncio
import logging
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

from core.config import (
    GATEWAY_HOST,
    GATEWAY_PORT,
    GATEWAY_PROXY_READ_TIMEOUT_SECONDS,
    HTTP_CONNECT_TIMEOUT_SECONDS,
    HTTP_POOL_TIMEOUT_SECONDS,
    HTTP_WRITE_TIMEOUT_SECONDS,
    LOG_LEVEL,
    SERVICES,
)
from core.logger import setup_logging
from core.network import build_service_base_url, normalize_bind_host


ROOT = Path(__file__).parent.parent
setup_logging("gateway")
logger = logging.getLogger(__name__)

_processes: dict[str, subprocess.Popen] = {}
SERVICE_PREFIX_MAP = {str(cfg["prefix"]): name for name, cfg in SERVICES.items()}


def _service_app_key(service_name: str) -> str:
    module_path = SERVICES[service_name]["script"].replace("\\", "/").replace("/", ".")
    module_name = module_path.removesuffix(".py")
    return f"{module_name}:api"


def _service_proxy_url(service_name: str, path: str) -> str:
    cfg = SERVICES[service_name]
    return f"{build_service_base_url(cfg['url'], cfg['port'])}/{path}"


def _proxy_timeout(service_name: str) -> httpx.Timeout:
    read_timeout = float(GATEWAY_PROXY_READ_TIMEOUT_SECONDS.get(service_name, 30.0))
    return httpx.Timeout(
        connect=HTTP_CONNECT_TIMEOUT_SECONDS,
        read=read_timeout,
        write=HTTP_WRITE_TIMEOUT_SECONDS,
        pool=HTTP_POOL_TIMEOUT_SECONDS,
    )


def start_services() -> None:
    for name, cfg in SERVICES.items():
        app_path = _service_app_key(name)
        host = normalize_bind_host(str(cfg["url"]))
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_services()
    await asyncio.sleep(1.5)
    print(f"[GATEWAY] ready - services: {list(_processes.keys())}")
    yield
    stop_services()


app = FastAPI(title="juldyz-gateway", lifespan=lifespan)


async def _proxy(service: str, path: str, request: Request):
    cfg = SERVICES.get(service)
    if not cfg:
        return JSONResponse({"error": f"unknown service '{service}'"}, status_code=404)

    url = _service_proxy_url(service, path)
    body = await request.body()
    headers = {"Content-Type": request.headers.get("Content-Type", "application/json")}

    try:
        async with httpx.AsyncClient(timeout=_proxy_timeout(service)) as client:
            response = await client.request(
                method=request.method,
                url=url,
                content=body,
                headers=headers,
            )
    except httpx.ConnectError:
        logger.exception(
            "Gateway upstream connect failed service=%s method=%s path=%s url=%s",
            service,
            request.method,
            path,
            url,
        )
        return JSONResponse({"status": "error", "detail": f"{service} is not reachable"}, status_code=502)
    except httpx.TimeoutException as exc:
        logger.exception(
            "Gateway upstream timeout service=%s method=%s path=%s url=%s error_type=%s",
            service,
            request.method,
            path,
            url,
            type(exc).__name__,
        )
        return JSONResponse(
            {"status": "error", "detail": f"{service} timed out ({type(exc).__name__})"},
            status_code=504,
        )
    except httpx.RequestError as exc:
        logger.exception(
            "Gateway upstream request failed service=%s method=%s path=%s url=%s error_type=%s",
            service,
            request.method,
            path,
            url,
            type(exc).__name__,
        )
        return JSONResponse(
            {"status": "error", "detail": f"{service} request failed: {type(exc).__name__}"},
            status_code=502,
        )

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


@app.post("/form-submit")
async def form_submit(request: Request):
    return await _proxy("form-service", "form-submit", request)


@app.api_route("/{service_prefix}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def prefix_proxy(service_prefix: str, path: str, request: Request):
    service_name = SERVICE_PREFIX_MAP.get(service_prefix)
    if not service_name:
        return JSONResponse({"error": f"unknown service prefix '{service_prefix}'"}, status_code=404)
    return await _proxy(service_name, path, request)


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
