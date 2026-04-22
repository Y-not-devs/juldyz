from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
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

# Helpers
def _service_app_key(service_name: str) -> str:
    script = SERVICES[service_name]["script"]
    module = Path(script).with_suffix("").as_posix().replace("/", ".")
    return f"{module}:api"


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


# Service lifecycle
def _start_service(name: str) -> subprocess.Popen:
    cfg = SERVICES[name]
    app_path = _service_app_key(name)
    host = normalize_bind_host(str(cfg["url"]))
    port = cfg["port"]
    log_level = cfg["log_level"]
    logger.info("Starting service %s on %s:%s", name, host, port)
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            app_path,
            "--host", host,
            "--port", str(port),
            "--log-level", log_level,
        ],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )


async def _wait_for_service(name: str, retries: int = 20, delay: float = 0.5) -> bool:
    cfg = SERVICES[name]
    url = f"{build_service_base_url(cfg['url'], cfg['port'])}/health"
    for attempt in range(1, retries + 1):
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(url)
                if resp.status_code < 500:
                    logger.info("Service %s is up (attempt %d)", name, attempt)
                    return True
        except httpx.RequestError:
            pass
        await asyncio.sleep(delay)
    logger.warning("Service %s did not become reachable after %d attempts", name, retries)
    return False


def start_services() -> None:
    for name in SERVICES:
        _processes[name] = _start_service(name)


async def wait_for_all_services() -> None:
    tasks = [_wait_for_service(name) for name in SERVICES]
    results = await asyncio.gather(*tasks)
    for name, ok in zip(SERVICES.keys(), results):
        if not ok:
            logger.error("Service %s failed to start — requests will likely get 502", name)


async def stop_services() -> None:
    loop = asyncio.get_event_loop()
    for name, proc in _processes.items():
        logger.info("Stopping service %s", name)
        try:
            proc.terminate()
            await loop.run_in_executor(None, lambda p=proc: p.wait(timeout=5))
        except Exception:
            proc.kill()



# FastAPI app with lifespan handling
@asynccontextmanager
async def lifespan(app: FastAPI):
    start_services()
    await wait_for_all_services()
    logger.info("Gateway ready — services: %s", list(_processes.keys()))
    try:
        yield
    finally:
        await stop_services()


app = FastAPI(title="juldyz-gateway", lifespan=lifespan)


# Proxy core
async def _proxy(service: str, path: str, request: Request) -> JSONResponse:
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
            service, request.method, path, url,
        )
        return JSONResponse(
            {"status": "error", "detail": f"{service} is not reachable"},
            status_code=502,
        )
    except httpx.TimeoutException as exc:
        logger.exception(
            "Gateway upstream timeout service=%s method=%s path=%s url=%s error_type=%s",
            service, request.method, path, url, type(exc).__name__,
        )
        return JSONResponse(
            {"status": "error", "detail": f"{service} timed out ({type(exc).__name__})"},
            status_code=504,
        )
    except httpx.RequestError as exc:
        logger.exception(
            "Gateway upstream request failed service=%s method=%s path=%s url=%s error_type=%s",
            service, request.method, path, url, type(exc).__name__,
        )
        return JSONResponse(
            {"status": "error", "detail": f"{service} request failed: {type(exc).__name__}"},
            status_code=502,
        )

    try:
        content = response.json()
    except Exception:
        # Upstream returned non-JSON — always 502 regardless of upstream status,
        # because returning e.g. 200 with an error body confuses clients.
        logger.warning(
            "Upstream non-JSON response service=%s status=%d body_preview=%s",
            service, response.status_code, response.text[:200],
        )
        return JSONResponse(
            {
                "status": "error",
                "detail": "upstream returned non-JSON",
                "upstream_status": response.status_code,
                "body": response.text[:200],
            },
            status_code=502,
        )

    return JSONResponse(status_code=response.status_code, content=content)

# Routes
@app.get("/health")
async def health() -> dict[str, Any]:
    status = [
        {
            "name": name,
            "url": f"{cfg['url']}:{cfg['port']}",
            "log_level": cfg["log_level"],
            "running": name in _processes and _processes[name].poll() is None,
        }
        for name, cfg in SERVICES.items()
    ]
    return {"gateway": "ok", "services": status}


@app.api_route(
    "/api/{service}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def api_proxy(service: str, path: str, request: Request) -> JSONResponse:
    return await _proxy(service, path, request)


@app.api_route(
    "/{service_prefix}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def prefix_proxy(service_prefix: str, path: str, request: Request) -> JSONResponse:
    service_name = SERVICE_PREFIX_MAP.get(service_prefix)
    if not service_name:
        return JSONResponse(
            {"error": f"unknown service prefix '{service_prefix}'"}, status_code=404
        )
    return await _proxy(service_name, path, request)


if __name__ == "__main__":
    uvicorn.run(app, host=GATEWAY_HOST, port=GATEWAY_PORT, log_level=LOG_LEVEL)