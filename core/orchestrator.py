from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict
from fastapi import HTTPException
import asyncio
import httpx
from core.config import SERVICES


class Pipeline:
    """
    Represents a pipeline step for processing candidate data.
    Each step interacts with a specific service.
    """

    def __init__(self, service_url: str):
        self.service_url = service_url

    async def send_request(
        self, endpoint: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send an async HTTP request to the service."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.service_url}/{endpoint}", json=payload
                )
                response.raise_for_status()
                return response.json()
            except httpx.RequestError as e:
                raise HTTPException(status_code=500, detail=f"Service request failed: {e}")


class CandidateWorkflow:
    """
    Handles the candidate workflow triggered by form submission.
    """

    def __init__(self, services: Dict[str, str]):
        self.services = services
        self.bot_pipeline = Pipeline(services["bot"])
        self.scoring_pipeline = Pipeline(services["scoring"])
        self.llm_pipeline = Pipeline(services["llm"])
        self.parser_pipeline = Pipeline(services["parser"])

    async def process_form_submission(self, form_data: Dict[str, Any]):
        """
        Orchestrates the candidate workflow triggered by form submission.
        """
        candidate_id = form_data.get("candidate_id")

        # Step 1: Notify bot service
        await self.bot_pipeline.send_request(
            "notify", {"candidate_id": candidate_id, "status": "Under Review"}
        )

        # Step 2: Extract and send data to respective services
        activities = form_data.get("activities")
        achievements = form_data.get("achievements")
        essay = form_data.get("essay")
        youtube_link = form_data.get("youtube_link")

        scoring_task = asyncio.create_task(
            self.scoring_pipeline.send_request(
                "process",
                {"candidate_id": candidate_id, "activities": activities, "achievements": achievements},
            )
        )

        llm_task = asyncio.create_task(
            self.llm_pipeline.send_request(
                "analyze-essay", {"candidate_id": candidate_id, "essay": essay}
            )
        )

        parser_task = asyncio.create_task(
            self.parser_pipeline.send_request(
                "parse-video", {"candidate_id": candidate_id, "youtube_link": youtube_link}
            )
        )

        # Wait for LLM and parser results
        llm_result = await llm_task
        parser_result = await parser_task

        # Step 3: Send parser results to LLM for further analysis
        llm_video_task = asyncio.create_task(
            self.llm_pipeline.send_request(
                "analyze-video",
                {"candidate_id": candidate_id, "video_text": parser_result.get("text")},
            )
        )

        # Step 4: Send LLM essay analysis to scoring service
        scoring_essay_task = asyncio.create_task(
            self.scoring_pipeline.send_request(
                "review-essay",
                {"candidate_id": candidate_id, "essay_analysis": llm_result},
            )
        )

        # Wait for all tasks to complete
        llm_video_result = await llm_video_task
        scoring_essay_result = await scoring_essay_task
        scoring_result = await scoring_task

        # Step 5: Finalize candidate review and notify bot for live interview
        await self.bot_pipeline.send_request(
            "start-interview",
            {
                "candidate_id": candidate_id,
                "scoring_result": scoring_result,
                "essay_review": scoring_essay_result,
                "video_analysis": llm_video_result,
            },
        )


class Orchestrator:
    """
    Main orchestrator for handling workflows.
    """

    def __init__(self):
        # Extract service URLs from the SERVICES configuration
        self.workflow = CandidateWorkflow({
            "bot": f"{SERVICES['bot-service']['url']}:{SERVICES['bot-service']['port']}",
            "scoring": f"{SERVICES['scoring-service']['url']}:{SERVICES['scoring-service']['port']}",
            "llm": f"{SERVICES['llm-service']['url']}:{SERVICES['llm-service']['port']}",
            "parser": f"{SERVICES['parser-service']['url']}:{SERVICES['parser-service']['port']}",
        })

    async def handle_form_submission(self, form_data: Dict[str, Any]):
        """
        Handle form submission and trigger the candidate workflow.
        """
        await self.workflow.process_form_submission(form_data)
