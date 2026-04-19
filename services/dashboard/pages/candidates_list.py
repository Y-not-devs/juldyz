from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import streamlit as st

from core.dashboard_config import ensure_session_settings, load_dashboard_settings
from services.dashboard.candidates_data import (
    build_table_rows,
    candidate_display_name,
    fetch_candidates,
    row_matches,
    safe_json_load,
)

st.set_page_config(
    page_title="Candidates List",
    page_icon=":busts_in_silhouette:",
    layout="wide",
)

ensure_session_settings(st.session_state, load_dashboard_settings())
DB_PATH = Path(__file__).resolve().parents[3] / "data" / "juldyz.db"


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

rows = fetch_candidates(DB_PATH, limit=page_size)
if not rows:
    st.warning("No candidates found.")
    st.stop()

filtered = [
    row
    for row in rows
    if row_matches(row, search_text=search_text, only_scored=only_scored, min_score=min_score)
]

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

table_rows = build_table_rows(filtered)

st.subheader("Table")
st.dataframe(table_rows, use_container_width=True, hide_index=True)

st.subheader("Candidate Details")
labels = []
for row in filtered:
    name = candidate_display_name(row) or "unknown"
    labels.append(f"{row.get('user_id')} | {name}")

selected_label = st.selectbox("Select candidate", options=labels)
selected_id = int(selected_label.split("|")[0].strip())
selected = next(row for row in filtered if int(row["user_id"]) == selected_id)
selected_score_display = (
    f"{float(selected['total_score']):.2f} / 10"
    if selected.get("total_score") is not None
    else "- / 10"
)

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
    st.write(f"**Processing Status:** {selected.get('processing_status')}")
    st.write(f"**Total Score:** {selected_score_display}")
    st.write(f"**AI Suspicion:** {selected.get('ai_suspicion')}")
    st.write(f"**Scored At:** {selected.get('scored_at')}")

if selected.get("processing_error"):
    st.error(f"Processing Error: {selected.get('processing_error')}")

with st.expander("Application Details", expanded=False):
    st.write("**Personal Presentation**")
    st.write(selected.get("personal_presentation") or "-")
    st.write("**English Results**")
    st.write(selected.get("english_results") or "-")
    st.write("**English Test Certificate**")
    st.write(selected.get("english_test_certificate") or "-")
    st.write("**Additional Documents**")
    st.write(selected.get("additional_documents") or "-")
    st.write("**Honor Certificate Upload**")
    st.write(selected.get("social_certificate") or "-")
    st.write("**Additional Info**")
    st.write(selected.get("additional_info") or "-")
    st.write("**Processing Started At**")
    st.write(selected.get("processing_started_at") or "-")
    st.write("**Processed At**")
    st.write(selected.get("processed_at") or "-")
    st.write("**Parser Status**")
    st.write(selected.get("parser_status") or "-")
    st.write("**Scoring Status**")
    st.write(selected.get("scoring_status") or "-")
    st.write("**Notification Status**")
    st.write(selected.get("notification_status") or "-")

if selected.get("parser_error"):
    st.error(f"Parser Error: {selected.get('parser_error')}")
if selected.get("scoring_error"):
    st.error(f"Scoring Error: {selected.get('scoring_error')}")
if selected.get("notification_error"):
    st.error(f"Notification Error: {selected.get('notification_error')}")

with st.expander("Form Raw Payload", expanded=bool(st.session_state["show_raw_payloads"])):
    st.json(safe_json_load(selected.get("raw_payload")))

