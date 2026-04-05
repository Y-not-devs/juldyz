from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
STORE_DIR = ROOT_DIR / "data" / "dashboard"
SETTINGS_PATH = STORE_DIR / "settings.json"
GRADING_CRITERIA_PATH = STORE_DIR / "grading_criteria.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "api_base_url": "http://localhost:8000",
    "prefixes": {
        "form": "form-service",
        "parser": "parser-service",
        "scoring": "scoring-service",
        "llm": "llm-service",
        "bot": "bot-service",
        "dashboard": "dashboard-service",
    },
    "ui": {
        "candidate_page_size": 50,
        "show_raw_payloads": False,
    },
}


def _deep_merge_dict(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_dashboard_settings() -> dict[str, Any]:
    data: dict[str, Any] = {}
    if SETTINGS_PATH.exists():
        try:
            raw = SETTINGS_PATH.read_text(encoding="utf-8")
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                data = parsed
        except Exception:
            data = {}
    return _deep_merge_dict(DEFAULT_SETTINGS, data)


def save_dashboard_settings(settings: dict[str, Any]) -> tuple[bool, str]:
    try:
        STORE_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True, str(SETTINGS_PATH)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def ensure_session_settings(session_state: Any, settings: dict[str, Any] | None = None) -> None:
    cfg = settings or load_dashboard_settings()
    prefixes = cfg.get("prefixes", {})
    ui_cfg = cfg.get("ui", {})

    session_defaults = {
        "api_base_url": cfg.get("api_base_url", DEFAULT_SETTINGS["api_base_url"]),
        "form_prefix": prefixes.get("form", DEFAULT_SETTINGS["prefixes"]["form"]),
        "parser_prefix": prefixes.get("parser", DEFAULT_SETTINGS["prefixes"]["parser"]),
        "scoring_prefix": prefixes.get("scoring", DEFAULT_SETTINGS["prefixes"]["scoring"]),
        "llm_prefix": prefixes.get("llm", DEFAULT_SETTINGS["prefixes"]["llm"]),
        "bot_prefix": prefixes.get("bot", DEFAULT_SETTINGS["prefixes"]["bot"]),
        "dashboard_prefix": prefixes.get("dashboard", DEFAULT_SETTINGS["prefixes"]["dashboard"]),
        "candidate_page_size": int(ui_cfg.get("candidate_page_size", DEFAULT_SETTINGS["ui"]["candidate_page_size"])),
        "show_raw_payloads": bool(ui_cfg.get("show_raw_payloads", DEFAULT_SETTINGS["ui"]["show_raw_payloads"])),
    }

    for key, value in session_defaults.items():
        if key not in session_state:
            session_state[key] = value


def build_settings_from_session(session_state: Any) -> dict[str, Any]:
    return {
        "api_base_url": str(session_state.get("api_base_url", DEFAULT_SETTINGS["api_base_url"])).strip(),
        "prefixes": {
            "form": str(session_state.get("form_prefix", DEFAULT_SETTINGS["prefixes"]["form"])).strip(),
            "parser": str(session_state.get("parser_prefix", DEFAULT_SETTINGS["prefixes"]["parser"])).strip(),
            "scoring": str(session_state.get("scoring_prefix", DEFAULT_SETTINGS["prefixes"]["scoring"])).strip(),
            "llm": str(session_state.get("llm_prefix", DEFAULT_SETTINGS["prefixes"]["llm"])).strip(),
            "bot": str(session_state.get("bot_prefix", DEFAULT_SETTINGS["prefixes"]["bot"])).strip(),
            "dashboard": str(session_state.get("dashboard_prefix", DEFAULT_SETTINGS["prefixes"]["dashboard"])).strip(),
        },
        "ui": {
            "candidate_page_size": int(
                session_state.get(
                    "candidate_page_size",
                    DEFAULT_SETTINGS["ui"]["candidate_page_size"],
                )
            ),
            "show_raw_payloads": bool(
                session_state.get(
                    "show_raw_payloads",
                    DEFAULT_SETTINGS["ui"]["show_raw_payloads"],
                )
            ),
        },
    }
