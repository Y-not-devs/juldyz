from __future__ import annotations

from typing import Any, Dict
from fastapi import HTTPException
from urllib.parse import urlparse
import httpx
from core.config import SERVICES

from core.logger import setup_logging
setup_logging("orchestrator")
class Pipeline:
    """
    Represents a pipeline step for processing candidate data.
    Each step interacts with a specific service.
    """

    def __init__(self, service_url: str):
        self.service_url = service_url

    async def send_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send an async HTTP request to the service."""
        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                response = await client.post(
                    f"{self.service_url}/{endpoint}", json=payload
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Service {self.service_url}/{endpoint} returned {e.response.status_code}: {e.response.text[:300]}",
                )
            except httpx.RequestError as e:
                raise HTTPException(status_code=500, detail=f"Service request failed: {e}")


def _service_base_url(url: str, port: int) -> str:
    host = str(url).strip()
    if host.startswith("http://"):
        host_part = host[len("http://") :]
        scheme = "http://"
    elif host.startswith("https://"):
        host_part = host[len("https://") :]
        scheme = "https://"
    else:
        host_part = host
        scheme = "http://"

    if host_part == "0.0.0.0":
        host_part = "127.0.0.1"

    return f"{scheme}{host_part}:{int(port)}"


class CandidateWorkflow:
    """
    Handles the candidate workflow triggered by form submission.
    """

    def __init__(self, services: Dict[str, str]):
        self.services = services
        self.bot_pipeline = Pipeline(services["bot"])
        self.scoring_pipeline = Pipeline(services["scoring"])
        self.parser_pipeline = Pipeline(services["parser"])

    async def process_form_submission(self, form_data: Dict[str, Any]):
        """
        Orchestrates the candidate workflow triggered by form submission.
        """
        candidate_id = form_data.get("candidate_id")
        tg_id = str(form_data.get("tg_id", "")).strip()
        payload = form_data.get("data") if isinstance(form_data.get("data"), dict) else form_data
        payload = payload if isinstance(payload, dict) else {}

        essay_failure = payload.get(
            "Reflect on a situation where your efforts or plan significantly failed. How exactly did you analyze what happened, and what new strategy did you choose to move forward? (Max characters: 100)",
            "",
        )
        essay_beta = payload.get(
            'The concept of "perpetual beta" means a constant readiness to update your knowledge and admit mistakes. Describe a skill, idea, or project of yours that is currently in "perpetual beta." How exactly are you challenging yourself to improve it? (Max characters: 100)',
            "",
        )
        essay_text = "\n\n".join([str(x).strip() for x in [essay_failure, essay_beta] if str(x).strip()])

        youtube_url = ""
        for key in ("Personal Presentation (Foundation)", "Personal Presentation (Undergraduate)"):
            value = str(payload.get(key, "")).strip()
            if value:
                try:
                    host = (urlparse(value).hostname or "").lower()
                except Exception:
                    host = ""
                if "youtube.com" in host or "youtu.be" in host:
                    youtube_url = value
                    break

        parser_payload: Dict[str, Any] = {"user_id": str(candidate_id)}
        if youtube_url:
            parser_payload["youtube_url"] = youtube_url
        if essay_text:
            parser_payload["essay_text"] = essay_text

        parser_result: Dict[str, Any] = {}
        if len(parser_payload) > 1:
            parser_result = await self.parser_pipeline.send_request("parse", parser_payload)

        scoring_payload: Dict[str, Any] = {
            "candidate_id": str(candidate_id),
            "form_data": payload,
        }
        if parser_result:
            scoring_payload["parser_context"] = parser_result

        await self.scoring_pipeline.send_request("evaluate", scoring_payload)

        if tg_id:
            await self.bot_pipeline.send_request(
                "notify",
                {"tg_id": tg_id, "candidate_id": str(candidate_id)},
            )


class Orchestrator:
    """
    Main orchestrator for handling workflows.
    """

    def __init__(self, services_config: Dict[str, Any] | None = None):
        cfg = services_config or SERVICES
        self.workflow = CandidateWorkflow({
            "bot": _service_base_url(cfg["bot-service"]["url"], cfg["bot-service"]["port"]),
            "scoring": _service_base_url(cfg["scoring-service"]["url"], cfg["scoring-service"]["port"]),
            "llm": _service_base_url(cfg["llm-service"]["url"], cfg["llm-service"]["port"]),
            "parser": _service_base_url(cfg["parser-service"]["url"], cfg["parser-service"]["port"]),
        })

    async def handle_form_submission(self, form_data: Dict[str, Any]):
        """
        Handle form submission and trigger the candidate workflow.
        """
        await self.workflow.process_form_submission(form_data)
