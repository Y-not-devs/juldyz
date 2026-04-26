from __future__ import annotations

import inspect
import logging
import re
from typing import Any, Awaitable, Callable
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
from core.logger import setup_logging
from core.network import build_service_base_url

setup_logging("orchestrator")
logger = logging.getLogger(__name__)

StageCallback = Callable[[str, str, str | None], Any]


class ServiceError(Exception):
    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


def _summarize_payload(payload: dict[str, Any], max_items: int = 8, max_length: int = 400) -> str:
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


def json_safe_error(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload, dict) else None
    if isinstance(summary, dict):
        return f"parser completed_with_errors: {summary}"
    return str(payload)[:500]


def _build_timeout(service_name: str) -> httpx.Timeout:
    read_timeout = float(ORCHESTRATOR_SERVICE_READ_TIMEOUT_SECONDS.get(service_name, 30.0))
    return httpx.Timeout(
        connect=HTTP_CONNECT_TIMEOUT_SECONDS,
        read=read_timeout,
        write=HTTP_WRITE_TIMEOUT_SECONDS,
        pool=HTTP_POOL_TIMEOUT_SECONDS,
    )


async def _emit_stage(
    callback: StageCallback | None,
    stage: str,
    status: str,
    detail: str | None = None,
) -> None:
    if callback is None:
        return

    result = callback(stage, status, detail)
    if inspect.isawaitable(result):
        await result


async def _run_stage(
    stage: str,
    callback: StageCallback | None,
    operation: Callable[[], Awaitable[Any]],
) -> Any:
    await _emit_stage(callback, stage, "processing", None)
    try:
        result = await operation()
    except Exception as exc:
        await _emit_stage(callback, stage, "failed", str(exc))
        raise
    await _emit_stage(callback, stage, "done", None)
    return result


async def _run_parser_stage(
    callback: StageCallback | None,
    operation: Callable[[], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    await _emit_stage(callback, "parser", "processing", None)
    try:
        parser_result = await operation()
    except Exception as exc:
        await _emit_stage(callback, "parser", "failed", str(exc))
        raise

    parser_status = str(parser_result.get("status", "")).lower()
    if parser_status == "completed":
        await _emit_stage(callback, "parser", "done", None)
        return parser_result

    if parser_status == "completed_with_errors":
        await _emit_stage(callback, "parser", "partial", json_safe_error(parser_result))
        return parser_result

    detail = f"Parser service returned unsupported status: {parser_status or 'missing'}"
    await _emit_stage(callback, "parser", "failed", detail)
    raise ServiceError(detail)


class Pipeline:
    """
    Represents a pipeline step for processing candidate data.
    Each step interacts with a specific service.
    """

    def __init__(self, service_name: str, service_url: str):
        self.service_name = service_name
        self.service_url = service_url

    async def send_request(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
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
                    raise ServiceError(
                        f"Service {self.service_name}/{endpoint} returned invalid JSON: {type(exc).__name__}"
                    ) from exc

                if not isinstance(body, dict):
                    raise ServiceError(
                        f"Service {self.service_name}/{endpoint} returned invalid JSON payload"
                    )

                if str(body.get("status", "")).lower() == "error":
                    detail = body.get("detail") or body.get("error") or "unknown service error"
                    raise ServiceError(
                        f"Service {self.service_name}/{endpoint} failed: {detail}"
                    )

                return body
            except httpx.HTTPStatusError as exc:
                logger.exception(
                    "Upstream HTTP error service=%s endpoint=%s status=%s url=%s payload=%s",
                    self.service_name,
                    endpoint,
                    exc.response.status_code,
                    request_url,
                    payload_summary,
                )
                raise ServiceError(
                    f"Service {self.service_name}/{endpoint} returned "
                    f"{exc.response.status_code}: {exc.response.text[:300]}"
                ) from exc
            except httpx.TimeoutException as exc:
                phase = type(exc).__name__.replace("Timeout", "").lower() or "request"
                logger.exception(
                    "Upstream timeout service=%s endpoint=%s phase=%s url=%s payload=%s",
                    self.service_name,
                    endpoint,
                    phase,
                    request_url,
                    payload_summary,
                )
                raise ServiceError(
                    f"Service {self.service_name}/{endpoint} timed out during {phase} phase"
                ) from exc
            except httpx.RequestError as exc:
                logger.exception(
                    "Upstream request failed service=%s endpoint=%s error_type=%s url=%s payload=%s",
                    self.service_name,
                    endpoint,
                    type(exc).__name__,
                    request_url,
                    payload_summary,
                )
                raise ServiceError(
                    f"Service {self.service_name}/{endpoint} request failed: {type(exc).__name__}"
                ) from exc


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
    essay_task_result = essay_task.get("result")
    essay_result = essay_task_result if isinstance(essay_task_result, dict) else {}

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
            "analysis": essay_result.get("analysis"),
            "llm_parsed_ok": bool(essay_result.get("llm_parsed_ok")),
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

    def __init__(self, services: dict[str, str]):
        self.services = services
        self.bot_pipeline = Pipeline("bot-service", services["bot"])
        self.scoring_pipeline = Pipeline("scoring-service", services["scoring"])
        self.parser_pipeline = Pipeline("parser-service", services["parser"])

    async def process_form_submission(
        self,
        form_data: dict[str, Any],
        stage_callback: StageCallback | None = None,
    ) -> dict[str, Any]:
        """
        Orchestrates the candidate workflow triggered by form submission.
        """
        raw_candidate_id = form_data.get("candidate_id")
        candidate_id = str(raw_candidate_id).strip() if raw_candidate_id is not None else ""
        if not candidate_id:
            raise ValueError("candidate_id is required")

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

        parser_payload: dict[str, Any] = {"user_id": candidate_id}
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

        parser_result: dict[str, Any] = {}
        if len(parser_payload) > 1:
            async def _parse_candidate() -> dict[str, Any]:
                return await self.parser_pipeline.send_request("parse", parser_payload)

            parser_result = await _run_parser_stage(stage_callback, _parse_candidate)
        else:
            await _emit_stage(stage_callback, "parser", "skipped", None)

        candidate_profile = _build_candidate_profile(candidate_id, payload, parser_result)

        scoring_payload: dict[str, Any] = {
            "candidate_id": candidate_id,
            "candidate_profile": candidate_profile,
        }
        if parser_result:
            scoring_payload["parser_context"] = parser_result

        async def _score_candidate() -> dict[str, Any]:
            scoring_result = await self.scoring_pipeline.send_request("evaluate", scoring_payload)
            scoring_data = scoring_result.get("data")
            if not isinstance(scoring_data, dict):
                raise ServiceError("Scoring service returned invalid response body")

            persistence = scoring_data.get("persistence", {})
            if not bool(persistence.get("saved")):
                raise ServiceError(f"Scoring result for candidate_id={candidate_id} was not persisted")

            return scoring_result

        scoring_result = await _run_stage("scoring", stage_callback, _score_candidate)

        if tg_id:
            async def _send_notification() -> dict[str, Any]:
                return await self.bot_pipeline.send_request(
                    "notify",
                    {"tg_id": tg_id, "candidate_id": candidate_id},
                )

            await _run_stage("notification", stage_callback, _send_notification)
        else:
            await _emit_stage(stage_callback, "notification", "skipped", None)

        return {
            "parser_result": parser_result,
            "candidate_profile": candidate_profile,
            "scoring_result": scoring_result,
        }


class Orchestrator:
    """
    Main orchestrator for handling workflows.
    """

    def __init__(self, services_config: dict[str, Any] | None = None):
        cfg = services_config or SERVICES
        self.workflow = CandidateWorkflow(
            {
                "bot": build_service_base_url(cfg["bot-service"]["url"], cfg["bot-service"]["port"]),
                "scoring": build_service_base_url(
                    cfg["scoring-service"]["url"],
                    cfg["scoring-service"]["port"],
                ),
                "parser": build_service_base_url(
                    cfg["parser-service"]["url"],
                    cfg["parser-service"]["port"],
                ),
            }
        )

    async def handle_form_submission(
        self,
        form_data: dict[str, Any],
        stage_callback: StageCallback | None = None,
    ) -> dict[str, Any]:
        """
        Handle form submission and trigger the candidate workflow.
        """
        return await self.workflow.process_form_submission(form_data, stage_callback=stage_callback)
