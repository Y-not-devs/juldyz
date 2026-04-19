from __future__ import annotations

from typing import Any


CONTROL_KEYS = frozenset(
    {
        "tg_id",
        "candidate_id",
        "response_id",
        "processing_status",
        "detail",
        "status",
        "data",
    }
)

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "email": ("Email Address", "email"),
    "first_name": ("Name", "First Name"),
    "last_name": ("Surname", "Last Name"),
    "patronymic": ("Patronymic",),
    "dob": ("Date of Birth",),
    "mobile_phone": ("Mobile phone number",),
    "instagram": ("Instagram",),
    "telegram_handle": ("Telegram",),
    "whatsapp": ("WhatsApp",),
    "program_applied": (
        "Which program are you applying for?",
        "  Which program are you applying for?  ",
    ),
    "major": (
        "Please specify your intended major",
        "Please specify your intended major:",
        "Please specify your intended major:  ",
    ),
    "personal_presentation": (
        "Personal Presentation (Foundation)",
        "Personal Presentation (Undergraduate)",
    ),
    "english_results": (
        "English proficiency results (Foundation)",
        "English proficiency results (Undergraduate)",
    ),
    "english_test_certificate": (
        "Please submit the results of your English proficiency test",
        "Please submit the results of your English proficiency test (Undergraduate)",
        "Please submit the results of your English proficiency test (Foundation)",
    ),
    "additional_documents": (
        "Additional documents",
        "Additional documents ",
        "Additional documents (Undergraduate)",
        "Additional documents (Foundation)",
    ),
    "honor_certificate": (
        "If you want to upload its certificate.",
        "If you want to upload its certificate. ",
        "If you want to upload its certificate",
    ),
    "essay_failure": (
        "Reflect on a situation where your efforts or plan significantly failed. How exactly did you analyze what happened, and what new strategy did you choose to move forward? (Max characters: 100)",
        "Reflect on a situation where your efforts or plan significantly failed. How exactly did you analyze what happened, and what new strategy did you choose to move forward? (Max characters: 120)",
        "Reflect on a situation where your efforts or plan significantly failed. How exactly did you analyze what happened, and what new strategy did you choose to move forward? (Max words: 100)",
    ),
    "essay_beta": (
        'The concept of "perpetual beta" means a constant readiness to update your knowledge and admit mistakes. Describe a skill, idea, or project of yours that is currently in "perpetual beta." How exactly are you challenging yourself to improve it? (Max characters: 100)',
        'The concept of "perpetual beta" means a constant readiness to update your knowledge and admit mistakes. Describe a skill, idea, or project of yours that is currently in "perpetual beta." How exactly are you challenging yourself to improve it? (Max words: 100)',
        'The concept of "Jas Ulan" here means consistent readiness to update your knowledge and skills. Describe a skill, experience or issue in your life that currently is "outdated" for you. How exactly are you challenging yourself to improve it? (Max characters: 120)',
    ),
    "github_url": (
        "GitHub",
        "Github",
        "GitHub URL",
        "Github URL",
        "GitHub profile",
        "Github profile",
    ),
}


def first_non_empty(payload: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            if value.strip():
                return value
            continue
        return value
    return default


def get_field_value(payload: dict[str, Any], field_name: str, default: Any = "") -> Any:
    aliases = FIELD_ALIASES.get(field_name, ())
    return first_non_empty(payload, *aliases, default=default)


def normalize_form_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    normalized: dict[str, Any] = {}
    nested_data = payload.get("data")
    if isinstance(nested_data, dict):
        normalized.update(nested_data)

    for key, value in payload.items():
        if key in CONTROL_KEYS:
            continue
        normalized[key] = value

    return normalized
