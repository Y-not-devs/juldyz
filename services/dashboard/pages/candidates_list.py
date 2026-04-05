from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import streamlit as st

from core.dashboard_config import ensure_session_settings, load_dashboard_settings

st.set_page_config(
    page_title="Candidates List",
    page_icon=":busts_in_silhouette:",
    layout="wide",
)

ensure_session_settings(st.session_state, load_dashboard_settings())

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "juldyz.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_candidates(limit: int = 50) -> list[dict[str, Any]]:
    if not DB_PATH.exists():
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
        r.social_certificate,
        r.additional_info,
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

    with _connect() as conn:
        rows = conn.execute(query, (int(limit),)).fetchall()
    return [dict(row) for row in rows]


def _safe_json_load(raw: Any) -> Any:
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


st.title("Candidates List")
st.caption("Live data from SQLite (`data/juldyz.db`).")

if not DB_PATH.exists():
    st.error(f"Database not found: {DB_PATH}")
    st.stop()

with st.sidebar:
    st.subheader("Filters")
    page_size = int(
        st.number_input(
            "Rows",
            min_value=10,
            max_value=500,
            value=int(st.session_state["candidate_page_size"]),
            step=10,
        )
    )
    st.session_state["candidate_page_size"] = page_size

    search_text = st.text_input("Search", placeholder="name, email, telegram_id").strip().lower()
    only_scored = st.checkbox("Only scored", value=False)
    min_score = st.slider("Min score", min_value=0.0, max_value=10.0, value=0.0, step=0.1)

rows = _fetch_candidates(limit=page_size)
if not rows:
    st.warning("No candidates found.")
    st.stop()


def _row_match(row: dict[str, Any]) -> bool:
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


filtered = [row for row in rows if _row_match(row)]

if not filtered:
    st.warning("No candidates match current filters.")
    st.stop()

metric1, metric2, metric3 = st.columns(3)
with metric1:
    st.metric("Candidates", len(filtered))
with metric2:
    scored_count = sum(1 for row in filtered if row.get("total_score") is not None)
    st.metric("Scored", scored_count)
with metric3:
    if scored_count:
        avg_score = round(sum(float(row["total_score"]) for row in filtered if row.get("total_score") is not None) / scored_count, 2)
        st.metric("Average Score", avg_score)
    else:
        st.metric("Average Score", "-")

table_rows = []
for row in filtered:
    name = (
        f"{row.get('form_first_name') or ''} {row.get('form_last_name') or ''}".strip()
        or f"{row.get('tg_first_name') or ''} {row.get('tg_last_name') or ''}".strip()
        or "-"
    )
    table_rows.append(
        {
            "user_id": row.get("user_id"),
            "name": name,
            "telegram_id": row.get("telegram_id"),
            "username": row.get("username"),
            "email": row.get("email"),
            "program": row.get("program_applied"),
            "major": row.get("major"),
            "score": row.get("total_score"),
            "scored_at": row.get("scored_at"),
        }
    )

st.subheader("Table")
st.dataframe(table_rows, use_container_width=True, hide_index=True)

st.subheader("Candidate Details")
labels = []
for row in filtered:
    name = (
        f"{row.get('form_first_name') or ''} {row.get('form_last_name') or ''}".strip()
        or f"{row.get('tg_first_name') or ''} {row.get('tg_last_name') or ''}".strip()
        or "unknown"
    )
    labels.append(f"{row.get('user_id')} | {name}")

selected_label = st.selectbox("Select candidate", options=labels)
selected_id = int(selected_label.split("|")[0].strip())
selected = next(row for row in filtered if int(row["user_id"]) == selected_id)

info_col1, info_col2, info_col3 = st.columns(3)
with info_col1:
    st.write(f"**User ID:** {selected.get('user_id')}")
    st.write(f"**Telegram ID:** {selected.get('telegram_id')}")
    st.write(f"**Username:** {selected.get('username')}")
with info_col2:
    st.write(f"**Email:** {selected.get('email')}")
    st.write(f"**Program:** {selected.get('program_applied')}")
    st.write(f"**Major:** {selected.get('major')}")
with info_col3:
    st.write(f"**Total Score:** {selected.get('total_score')}")
    st.write(f"**AI Suspicion:** {selected.get('ai_suspicion')}")
    st.write(f"**Scored At:** {selected.get('scored_at')}")

with st.expander("Application Details", expanded=False):
    st.write("**Personal Presentation**")
    st.write(selected.get("personal_presentation") or "-")
    st.write("**English Results**")
    st.write(selected.get("english_results") or "-")
    st.write("**Social Certificate**")
    st.write(selected.get("social_certificate") or "-")
    st.write("**Additional Info**")
    st.write(selected.get("additional_info") or "-")

with st.expander("Form Raw Payload", expanded=bool(st.session_state["show_raw_payloads"])):
    st.json(_safe_json_load(selected.get("raw_payload")))

