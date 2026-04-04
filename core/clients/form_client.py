from __future__ import annotations

from typing import Any

from core.clients.base import ServiceClient


class FormClient(ServiceClient):
    def __init__(self):
        super().__init__(service_name="form-service")

    async def submit_form(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.post("/form-submit", payload)
