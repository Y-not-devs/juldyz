from __future__ import annotations

import json
from typing import Any

from core.db import Database, db


def fetch_candidates(limit: int = 50, database: Database | None = None) -> list[dict[str, Any]]:
    storage = database or db
    return storage.get_candidate_dashboard_rows(limit=limit)


def safe_json_load(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return text


def candidate_display_name(row: dict[str, Any]) -> str:
    return (
        f"{row.get('form_first_name') or ''} {row.get('form_last_name') or ''}".strip()
        or f"{row.get('tg_first_name') or ''} {row.get('tg_last_name') or ''}".strip()
        or "-"
    )


def row_matches(
    row: dict[str, Any],
    *,
    search_text: str = "",
    only_scored: bool = False,
    min_score: float = 0.0,
) -> bool:
    score = row.get("total_score")
    if only_scored and score is None:
        return False
    if score is not None and float(score) < min_score:
        return False
    if not search_text:
        return True

    full_name = f"{row.get('form_first_name') or ''} {row.get('form_last_name') or ''}".strip().lower()
    tg_name = f"{row.get('tg_first_name') or ''} {row.get('tg_last_name') or ''}".strip().lower()
    haystack = " | ".join(
        [
            str(row.get("telegram_id", "")),
            str(row.get("email", "")),
            str(row.get("username", "")),
            full_name,
            tg_name,
        ]
    ).lower()
    return search_text in haystack


def build_table_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    table_rows: list[dict[str, Any]] = []
    for row in rows:
        score = row.get("total_score")
        table_rows.append(
            {
                "user_id": row.get("user_id"),
                "name": candidate_display_name(row),
                "telegram_id": row.get("telegram_id"),
                "username": row.get("username"),
                "email": row.get("email"),
                "program": row.get("program_applied"),
                "major": row.get("major"),
                "processing_status": row.get("processing_status"),
                "score": score,
                "score_out_of": f"{float(score):.2f} / 10" if score is not None else "- / 10",
                "parser": row.get("parser_status"),
                "scoring": row.get("scoring_status"),
                "scored_at": row.get("scored_at"),
            }
        )
    return table_rows
