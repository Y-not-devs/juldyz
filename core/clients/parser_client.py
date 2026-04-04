from __future__ import annotations

from typing import Any

from core.clients.base import ServiceClient


class ParserClient(ServiceClient):
    def __init__(self):
        super().__init__(service_name="parser-service")

    async def parse(
        self,
        user_id: str,
        file_id: str | None = None,
        github_url: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"user_id": user_id}
        if file_id:
            payload["file_id"] = file_id
        if github_url:
            payload["github_url"] = github_url
        return await self.post("/parse", payload)
