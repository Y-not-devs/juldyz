from __future__ import annotations

from typing import Any

import httpx

from core.config import SERVICES


class ServiceClient:
    def __init__(self, service_name: str, timeout: float = 15.0):
        cfg = SERVICES[service_name]
        self._base_url = f"{cfg['url']}:{cfg['port']}"
        self._timeout = timeout

    async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", path, payload=payload)

    async def get(self, path: str) -> dict[str, Any]:
        return await self._request("GET", path, payload=None)

    async def _request(self, method: str, path: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        normalized_path = path if path.startswith("/") else f"/{path}"
        url = f"{self._base_url}{normalized_path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(method=method, url=url, json=payload)
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Service request failed: {url}. {exc}") from exc

        try:
            body = response.json()
        except ValueError:
            body = {"detail": response.text}

        if response.status_code >= 400:
            detail = body.get("detail", body)
            raise RuntimeError(f"Service returned {response.status_code}: {detail}")

        return body
