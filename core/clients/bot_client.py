from __future__ import annotations

from typing import Any

from core.clients.base import ServiceClient


class BotClient(ServiceClient):
    def __init__(self):
        super().__init__(service_name="bot-service")

    async def notify(self, tg_id: str, candidate_id: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"tg_id": tg_id}
        if candidate_id:
            payload["candidate_id"] = candidate_id
        return await self.post("/notify", payload)
