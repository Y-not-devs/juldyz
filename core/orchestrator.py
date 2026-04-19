from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict
from fastapi import HTTPException
from urllib.parse import urlparse
import httpx
from core.config import (
    HTTP_CONNECT_TIMEOUT_SECONDS,
    HTTP_POOL_TIMEOUT_SECONDS,
    HTTP_WRITE_TIMEOUT_SECONDS,
    ORCHESTRATOR_SERVICE_READ_TIMEOUT_SECONDS,
    SERVICES,
)
from core.form_fields import FIELD_ALIASES, get_field_value, normalize_form_payload
from core.network import build_service_base_url

from core.logger import setup_logging
setup_logging("orchestrator")
logger = logging.getLogger(__name__)


def _summarize_payload(payload: Dict[str, Any], max_items: int = 8, max_length: int = 400) -> str:
    summary_parts: list[str] = []
    for key in list(payload.keys())[:max_items]:
        value = payload.get(key)
        if isinstance(value, str):
            rendered = value[:80]
        elif isinstance(value, list):
            rendered = f"list[{len(value)}]"
        elif isinstance(value, dict):
            rendered = f"dict[{len(value)}]"
        else:
            rendered = str(value)
        summary_parts.append(f"{key}={rendered}")
    return "; ".join(summary_parts)[:max_length]


def _build_timeout(service_name: str) -> httpx.Timeout:
    read_timeout = float(ORCHESTRATOR_SERVICE_READ_TIMEOUT_SECONDS.get(service_name, 30.0))
    return httpx.Timeout(
        connect=HTTP_CONNECT_TIMEOUT_SECONDS,
        read=read_timeout,
        write=HTTP_WRITE_TIMEOUT_SECONDS,
        pool=HTTP_POOL_TIMEOUT_SECONDS,
    )


class Pipeline:
    """
    Represents a pipeline step for processing candidate data.
    Each step interacts with a specific service.
    """

    def __init__(self, service_name: str, service_url: str):
        self.service_name = service_name
        self.service_url = service_url

    async def send_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send an async HTTP request to the service."""
        request_url = f"{self.service_url}/{endpoint}"
        payload_summary = _summarize_payload(payload)
        timeout = _build_timeout(self.service_name)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.post(request_url, json=payload)
                response.raise_for_status()
                try:
                    body = response.json()
                except ValueError as exc:
                    logger.exception(
                        "Upstream returned invalid JSON service=%s endpoint=%s url=%s payload=%s",
                        self.service_name,
                        endpoint,
                        request_url,
                        payload_summary,
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=f"Service {self.service_name}/{endpoint} returned invalid JSON: {type(exc).__name__}",
                    ) from exc
                if not isinstance(body, dict):
                    raise HTTPException(
                        status_code=500,
                        detail=f"Service {self.service_name}/{endpoint} returned invalid JSON payload",
                    )
                if str(body.get("status", "")).lower() == "error":
                    detail = body.get("detail") or body.get("error") or "unknown service error"
                    raise HTTPException(
                        status_code=500,
                        detail=f"Service {self.service_name}/{endpoint} failed: {detail}",
                    )
                return body
            except httpx.HTTPStatusError as e:
                logger.exception(
                    "Upstream HTTP error service=%s endpoint=%s status=%s url=%s payload=%s",
                    self.service_name,
                    endpoint,
                    e.response.status_code,
                    request_url,
                    payload_summary,
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"Service {self.service_name}/{endpoint} returned {e.response.status_code}: {e.response.text[:300]}",
                )
            except httpx.TimeoutException as e:
                phase = type(e).__name__.replace("Timeout", "").lower() or "request"
                logger.exception(
                    "Upstream timeout service=%s endpoint=%s phase=%s url=%s payload=%s",
                    self.service_name,
                    endpoint,
                    phase,
                    request_url,
                    payload_summary,
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"Service {self.service_name}/{endpoint} timed out during {phase} phase",
                ) from e
            except httpx.RequestError as e:
                logger.exception(
                    "Upstream request failed service=%s endpoint=%s error_type=%s url=%s payload=%s",
                    self.service_name,
                    endpoint,
                    type(e).__name__,
                    request_url,
                    payload_summary,
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"Service {self.service_name}/{endpoint} request failed: {type(e).__name__}",
                ) from e


def _extract_urls(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        values = value
    else:
        values = [value]

    urls: list[str] = []
    for item in values:
        text = str(item).strip()
        if not text:
            continue
        urls.extend(re.findall(r"https?://[^\s,]+", text))
    return urls


def _extract_github_url(payload: dict[str, Any]) -> str:
    explicit_keys = FIELD_ALIASES["github_url"]
    for key in explicit_keys:
        for url in _extract_urls(payload.get(key)):
            host = (urlparse(url).hostname or "").lower()
            if "github.com" in host:
                return url

    for value in payload.values():
        for url in _extract_urls(value):
            host = (urlparse(url).hostname or "").lower()
            if "github.com" in host:
                return url
    return ""


def _extract_pdf_source(payload: dict[str, Any]) -> dict[str, str]:
    explicit_upload_keys = (
        *FIELD_ALIASES["additional_documents"],
        *FIELD_ALIASES["english_test_certificate"],
    )

    for key in explicit_upload_keys:
        raw_value = payload.get(key)
        if raw_value is None:
            continue
        text = str(raw_value).strip()
        if not text:
            continue
        for url in _extract_urls(text):
            if url.lower().endswith(".pdf") or "drive.google.com" in url.lower():
                return {"file_id": "", "file_url": url}
        if re.fullmatch(r"[A-Za-z0-9_-]{6,128}", text):
            return {"file_id": text, "file_url": ""}
    return {"file_id": "", "file_url": ""}


def _normalize_parser_task(task_payload: Any) -> dict[str, Any]:
    if not isinstance(task_payload, dict):
        return {"status": "UNAVAILABLE", "result": None}
    return {
        "status": str(task_payload.get("status", "UNAVAILABLE")).upper(),
        "result": task_payload.get("result"),
        "error": task_payload.get("error"),
        "error_type": task_payload.get("error_type"),
    }


def _build_candidate_profile(
    candidate_id: Any,
    payload: dict[str, Any],
    parser_result: dict[str, Any],
) -> dict[str, Any]:
    results = parser_result.get("results", {}) if isinstance(parser_result, dict) else {}
    essay_task = _normalize_parser_task(results.get("essay_task"))
    video_task = _normalize_parser_task(results.get("video_task"))
    pdf_task = _normalize_parser_task(results.get("file_task"))
    github_task = _normalize_parser_task(results.get("github_task"))

    return {
        "candidate_id": str(candidate_id),
        "form": {
            "first_name": get_field_value(payload, "first_name"),
            "last_name": get_field_value(payload, "last_name"),
            "program_applied": get_field_value(payload, "program_applied"),
            "major": get_field_value(payload, "major"),
            "personal_presentation": get_field_value(payload, "personal_presentation"),
            "english_results": get_field_value(payload, "english_results"),
            "raw": payload,
        },
        "essay": {
            "text_failure": get_field_value(payload, "essay_failure"),
            "text_beta": get_field_value(payload, "essay_beta"),
            "task_status": essay_task["status"],
            "analysis": (essay_task.get("result") or {}).get("analysis") if isinstance(essay_task.get("result"), dict) else None,
            "llm_parsed_ok": bool((essay_task.get("result") or {}).get("llm_parsed_ok")) if isinstance(essay_task.get("result"), dict) else False,
            "error": essay_task.get("error"),
        },
        "video": {
            "task_status": video_task["status"],
            "data": video_task.get("result"),
            "error": video_task.get("error"),
        },
        "pdf": {
            "task_status": pdf_task["status"],
            "data": pdf_task.get("result"),
            "error": pdf_task.get("error"),
        },
        "github": {
            "task_status": github_task["status"],
            "data": github_task.get("result"),
            "error": github_task.get("error"),
        },
    }


class CandidateWorkflow:
    """
    Handles the candidate workflow triggered by form submission.
    """

    def __init__(self, services: Dict[str, str]):
        self.services = services
        self.bot_pipeline = Pipeline("bot-service", services["bot"])
        self.scoring_pipeline = Pipeline("scoring-service", services["scoring"])
        self.parser_pipeline = Pipeline("parser-service", services["parser"])

    async def process_form_submission(
        self,
        form_data: Dict[str, Any],
        stage_callback: Callable[[str, str, str | None], None] | None = None,
    ):
        """
        Orchestrates the candidate workflow triggered by form submission.
        """
        candidate_id = form_data.get("candidate_id")
        tg_id = str(form_data.get("tg_id", "")).strip()
        payload = normalize_form_payload(form_data)

        essay_failure = get_field_value(payload, "essay_failure", "")
        essay_beta = get_field_value(payload, "essay_beta", "")
        essay_text = "\n\n".join([str(x).strip() for x in [essay_failure, essay_beta] if str(x).strip()])

        youtube_url = str(get_field_value(payload, "personal_presentation", "")).strip()
        if youtube_url:
            try:
                host = (urlparse(youtube_url).hostname or "").lower()
            except Exception:
                host = ""
            if "youtube.com" not in host and "youtu.be" not in host:
                youtube_url = ""

        github_url = _extract_github_url(payload)
        pdf_source = _extract_pdf_source(payload)

        parser_payload: Dict[str, Any] = {"user_id": str(candidate_id)}
        if youtube_url:
            parser_payload["youtube_url"] = youtube_url
        if essay_text:
            parser_payload["essay_text"] = essay_text
        if github_url:
            parser_payload["github_url"] = github_url
        if pdf_source.get("file_id"):
            parser_payload["file_id"] = pdf_source["file_id"]
        if pdf_source.get("file_url"):
            parser_payload["file_url"] = pdf_source["file_url"]

        parser_result: Dict[str, Any] = {}
        if len(parser_payload) > 1:
            if stage_callback:
                stage_callback("parser", "processing", None)
            parser_result = await self.parser_pipeline.send_request("parse", parser_payload)
            parser_status = str(parser_result.get("status", "")).lower()
            if stage_callback:
                if parser_status == "completed":
                    stage_callback("parser", "done", None)
                else:
                    stage_callback("parser", "failed", json_safe_error(parser_result))
        elif stage_callback:
            stage_callback("parser", "skipped", None)

        candidate_profile = _build_candidate_profile(candidate_id, payload, parser_result)

        scoring_payload: Dict[str, Any] = {
            "candidate_id": str(candidate_id),
            "candidate_profile": candidate_profile,
        }
        if parser_result:
            scoring_payload["parser_context"] = parser_result
        if payload:
            scoring_payload["form_data"] = payload

        if stage_callback:
            stage_callback("scoring", "processing", None)
        scoring_result = await self.scoring_pipeline.send_request("evaluate", scoring_payload)
        scoring_data = scoring_result.get("data")
        if not isinstance(scoring_data, dict):
            if stage_callback:
                stage_callback("scoring", "failed", "Scoring service returned invalid response body")
            raise HTTPException(
                status_code=500,
                detail="Scoring service returned invalid response body",
            )
        persistence = scoring_data.get("persistence", {})
        if candidate_id is not None and not bool(persistence.get("saved")):
            if stage_callback:
                stage_callback("scoring", "failed", f"Scoring result for candidate_id={candidate_id} was not persisted")
            raise HTTPException(
                status_code=500,
                detail=f"Scoring result for candidate_id={candidate_id} was not persisted",
            )
        if stage_callback:
            stage_callback("scoring", "done", None)

        if tg_id:
            if stage_callback:
                stage_callback("notification", "processing", None)
            await self.bot_pipeline.send_request(
                "notify",
                {"tg_id": tg_id, "candidate_id": str(candidate_id)},
            )
            if stage_callback:
                stage_callback("notification", "done", None)
        elif stage_callback:
            stage_callback("notification", "skipped", None)

        return {
            "parser_result": parser_result,
            "candidate_profile": candidate_profile,
            "scoring_result": scoring_result,
        }


class Orchestrator:
    """
    Main orchestrator for handling workflows.
    """

    def __init__(self, services_config: Dict[str, Any] | None = None):
        cfg = services_config or SERVICES
        self.workflow = CandidateWorkflow({
            "bot": build_service_base_url(cfg["bot-service"]["url"], cfg["bot-service"]["port"]),
            "scoring": build_service_base_url(cfg["scoring-service"]["url"], cfg["scoring-service"]["port"]),
            "llm": build_service_base_url(cfg["llm-service"]["url"], cfg["llm-service"]["port"]),
            "parser": build_service_base_url(cfg["parser-service"]["url"], cfg["parser-service"]["port"]),
        })

    async def handle_form_submission(
        self,
        form_data: Dict[str, Any],
        stage_callback: Callable[[str, str, str | None], None] | None = None,
    ):
        """
        Handle form submission and trigger the candidate workflow.
        """
        return await self.workflow.process_form_submission(form_data, stage_callback=stage_callback)


def json_safe_error(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload, dict) else None
    if isinstance(summary, dict):
        return f"parser completed_with_errors: {summary}"
    return str(payload)[:500]
