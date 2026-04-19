from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "juldyz.db"


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def fetch_candidates(db_path: Path | str = DEFAULT_DB_PATH, limit: int = 50) -> list[dict[str, Any]]:
    path = Path(db_path)
    if not path.exists():
        return []

    query = """
    SELECT
        u.id AS user_id,
        u.telegram_id,
        u.created_at,
        t.username,
        t.first_name AS tg_first_name,
        t.last_name AS tg_last_name,
        r.email,
        r.first_name AS form_first_name,
        r.last_name AS form_last_name,
        r.program_applied,
        r.major,
        r.personal_presentation,
        r.english_results,
        r.english_test_certificate,
        r.additional_documents,
        r.social_certificate,
        r.additional_info,
        r.processing_status,
        r.processing_error,
        r.processing_started_at,
        r.processed_at,
        r.parser_status,
        r.parser_error,
        r.scoring_status,
        r.scoring_error,
        r.notification_status,
        r.notification_error,
        r.raw_payload,
        s.total AS total_score,
        s.motivation,
        s.experience,
        s.leadership,
        s.growth,
        s.ai_suspicion,
        s.scored_at
    FROM users u
    LEFT JOIN telegram_users t
        ON t.telegram_id = u.telegram_id
    LEFT JOIN candidate_responses r
        ON r.id = (
            SELECT cr.id
            FROM candidate_responses cr
            WHERE cr.user_id = u.id
            ORDER BY cr.id DESC
            LIMIT 1
        )
    LEFT JOIN scores s
        ON s.user_id = u.id
    ORDER BY
        CASE WHEN s.total IS NULL THEN 1 ELSE 0 END,
        s.total DESC,
        u.id DESC
    LIMIT ?
    """

    with connect(path) as conn:
        rows = conn.execute(query, (int(limit),)).fetchall()
    return [dict(row) for row in rows]


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
