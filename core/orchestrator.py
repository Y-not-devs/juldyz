from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.events import SystemEvent
from core.pipelines import CandidatePipeline


@dataclass
class PipelineRegistry:
    candidate: CandidatePipeline


class Orchestrator:
    def __init__(self, pipelines: PipelineRegistry):
        self._pipelines = pipelines

    async def handle_event(self, event: SystemEvent) -> dict[str, Any]:
        if event.type == "form_completed":
            candidate_id = str(event.payload.get("candidate_id", "")).strip()
            if not candidate_id:
                raise ValueError("Missing candidate_id for form_completed event")
            form_payload = event.payload.get("form_payload", {})
            return await self._pipelines.candidate.run(candidate_id, form_payload)

        raise ValueError(f"Unsupported event type: {event.type}")
