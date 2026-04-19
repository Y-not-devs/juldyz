from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import re
from typing import Any

import httpx

from core.config import LLM_GENERATE_TIMEOUT_SECONDS, SERVICES
from core.network import build_service_base_url
from services.parser.storage import setup_user_directories, write_json_file
from services.parser.validation import ensure_safe_identifier

MAX_ESSAY_CHARS = 12000


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _build_llm_url() -> str:
    cfg = SERVICES["llm-service"]
    return f"{build_service_base_url(cfg['url'], cfg['port'])}/generate"


def _extract_json_candidate(text: str) -> str | None:
    cleaned = text.strip()
    if not cleaned:
        return None
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, flags=re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    first = cleaned.find("{")
    last = cleaned.rfind("}")
    if first != -1 and last != -1 and last > first:
        return cleaned[first : last + 1].strip()
    return None


def _parse_llm_response(response_text: str) -> dict[str, Any]:
    json_candidate = _extract_json_candidate(response_text)
    if not json_candidate:
        return {"parsed_ok": False, "analysis": None, "reason": "json_not_found"}
    try:
        parsed = json.loads(json_candidate)
        if isinstance(parsed, dict):
            return {"parsed_ok": True, "analysis": parsed, "reason": "ok"}
        return {"parsed_ok": False, "analysis": None, "reason": "json_not_object"}
    except Exception as exc:
        return {"parsed_ok": False, "analysis": None, "reason": f"json_parse_error:{type(exc).__name__}"}


def parse_essay_task(user_id: str, essay_text: str) -> dict:
    safe_user_id = ensure_safe_identifier(user_id, "user_id")
    essay = (essay_text or "").strip()
    if not essay:
        raise ValueError("essay_text is empty")
    if len(essay) > MAX_ESSAY_CHARS:
        raise ValueError(f"essay_text too long ({len(essay)}). max={MAX_ESSAY_CHARS}")

    instruction = (
        "Analyze this admissions essay. Return only JSON with keys: summary, "
        "scores, green_flags, red_flags, authenticity_signals, language_quality. "
        "scores should include 0-10 integers for growth_mindset, resilience, "
        "motivation_clarity, mission_alignment, authenticity_confidence."
    )
    llm_payload = {"instruction": instruction, "text": essay}

    llm_url = _build_llm_url()
    with httpx.Client(timeout=LLM_GENERATE_TIMEOUT_SECONDS) as client:
        resp = client.post(llm_url, json=llm_payload)
    if resp.status_code >= 400:
        raise RuntimeError(f"LLM HTTP {resp.status_code}: {resp.text[:300]}")

    body = resp.json() if resp.content else {}
    if not isinstance(body, dict):
        raise RuntimeError("Invalid LLM payload type")
    if body.get("error"):
        raise RuntimeError(f"LLM error: {body['error']}")

    raw_response = str(body.get("response", "")).strip()
    if not raw_response:
        raise RuntimeError("LLM returned empty response")
    parsed = _parse_llm_response(raw_response)

    dirs = setup_user_directories(safe_user_id)
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    output_path = dirs["processed"] / f"essay_{ts}.json"
    artifact = {
        "status": "analyzed",
        "user_id": safe_user_id,
        "essay_char_count": len(essay),
        "essay_sha256": hashlib.sha256(essay.encode("utf-8")).hexdigest(),
        "updated_at": _utc_now_iso(),
        "llm": {
            "url": llm_url,
            "parsed": parsed,
            "raw_response": raw_response,
        },
    }
    write_json_file(output_path, artifact)

    return {
        "status": "success",
        "user_id": safe_user_id,
        "essay_char_count": len(essay),
        "llm_parsed_ok": bool(parsed.get("parsed_ok")),
        "analysis": parsed.get("analysis"),
        "raw_response": raw_response,
        "output_path": str(output_path),
        "finished_at": _utc_now_iso(),
    }
