from __future__ import annotations

import asyncio
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
        youtube_url: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"user_id": user_id}
        if file_id:
            payload["file_id"] = file_id
        if github_url:
            payload["github_url"] = github_url
        if youtube_url:
            payload["youtube_url"] = youtube_url
        return await self.post("/parse", payload)

    async def get_task_status(self, task_id: str) -> dict[str, Any]:
        return await self.get(f"/parse/tasks/{task_id}")

    async def wait_for_tasks(
        self,
        task_ids: dict[str, str | None],
        timeout_seconds: float = 25.0,
        poll_interval_seconds: float = 1.0,
    ) -> dict[str, Any]:
        pending = {name: task_id for name, task_id in task_ids.items() if task_id}
        if not pending:
            return {"completed": {}, "timed_out": []}

        completed: dict[str, Any] = {}
        elapsed = 0.0
        while pending and elapsed < timeout_seconds:
            ready_keys: list[str] = []
            for name, task_id in pending.items():
                status_payload = await self.get_task_status(task_id)
                status = str(status_payload.get("status", "")).upper()
                if status in {"SUCCESS", "FAILURE"}:
                    completed[name] = status_payload
                    ready_keys.append(name)

            for name in ready_keys:
                pending.pop(name, None)

            if pending:
                await asyncio.sleep(poll_interval_seconds)
                elapsed += poll_interval_seconds

        return {"completed": completed, "timed_out": list(pending.keys())}
