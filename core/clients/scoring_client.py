from __future__ import annotations

from typing import Any

from core.clients.base import ServiceClient


class ScoringClient(ServiceClient):
    def __init__(self):
        super().__init__(service_name="scoring-service")

    async def evaluate(self, candidate_data: dict[str, Any]) -> dict[str, Any]:
        return await self.post("/evaluate", candidate_data)
