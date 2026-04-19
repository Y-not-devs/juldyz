from __future__ import annotations

import json

import httpx
import streamlit as st

from core.config import DASHBOARD_REQUEST_TIMEOUT_SECONDS
from core.dashboard_config import ensure_session_settings, load_dashboard_settings

st.set_page_config(
    page_title="Scoring Settings",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
)

ensure_session_settings(st.session_state, load_dashboard_settings())


def call_evaluate(base_url: str, prefix: str, payload: dict) -> tuple[bool, dict | str]:
    url = f"{base_url.rstrip('/')}/{prefix.strip('/')}/evaluate"
    try:
        with httpx.Client(timeout=DASHBOARD_REQUEST_TIMEOUT_SECONDS["scoring"]) as client:
            resp = client.post(url, json=payload)
        if resp.status_code >= 400:
            try:
                return False, resp.json()
            except Exception:
                return False, resp.text
        return True, resp.json() if resp.content else {}
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _list_from_count(prefix: str, count: int) -> list[str]:
    return [f"{prefix}_{idx + 1}" for idx in range(max(0, count))]


def _build_payload(
    activities_text: str,
    honors_text: str,
    essay_failure: str,
    essay_beta: str,
    transcript_available: bool,
    q5_level: str,
    coverage_ratio: float,
    mastery_count: int,
    autonomy_count: int,
    mission_count: int,
) -> dict:
    form_data = {
        "Activity type": activities_text,
        "Honors 1 title": honors_text,
        "Reflect on a situation where your efforts or plan significantly failed. How exactly did you analyze what happened, and what new strategy did you choose to move forward? (Max characters: 100)": essay_failure,
        'The concept of "perpetual beta" means a constant readiness to update your knowledge and admit mistakes. Describe a skill, idea, or project of yours that is currently in "perpetual beta." How exactly are you challenging yourself to improve it? (Max characters: 100)': essay_beta,
    }

    parser_context = {
        "results": {
            "video_task": {
                "status": "SUCCESS",
                "result": {
                    "transcript": {
                        "available": transcript_available,
                        "source": "manual_input",
                    },
                    "analysis": {
                        "question_coverage_ratio": float(coverage_ratio),
                        "question_coverage": [
                            {
                                "question_id": "q5_leadership",
                                "coverage_level": q5_level,
                            }
                        ],
                        "signals": {
                            "intrinsic": {
                                "signals": {
                                    "mastery_mentions": _list_from_count("mastery", mastery_count),
                                    "autonomy_mentions": _list_from_count("autonomy", autonomy_count),
                                }
                            },
                            "mission_alignment": {
                                "signal_count": int(mission_count),
                            },
                        },
                    },
                },
            }
        }
    }

    return {
        "form_data": form_data,
        "essay_failure": essay_failure,
        "essay_beta": essay_beta,
        "parser_context": parser_context,
    }


if "last_scoring_result" not in st.session_state:
    st.session_state["last_scoring_result"] = {}

st.title("Scoring Settings")
st.caption("Run scoring with explicit feature inputs and inspect explainable outputs.")

with st.sidebar:
    st.subheader("Scoring API")
    st.session_state["api_base_url"] = st.text_input(
        "API Base URL",
        value=str(st.session_state["api_base_url"]),
    ).strip() or "http://localhost:8000"
    st.session_state["scoring_prefix"] = st.text_input(
        "Scoring Prefix",
        value=str(st.session_state["scoring_prefix"]),
    ).strip() or "scoring-service"

left_col, right_col = st.columns([2, 1])

with left_col:
    with st.form("scoring_form"):
        st.subheader("Candidate Text Signals")
        activities_text = st.text_area(
            "Activities text",
            placeholder="captain robotics team for 3 years...",
            height=90,
        )
        honors_text = st.text_area(
            "Honors text",
            placeholder="winner of city olympiad...",
            height=90,
        )
        essay_failure = st.text_area(
            "Essay: reaction to failure",
            placeholder="I analyzed root cause and changed strategy...",
            height=90,
        )
        essay_beta = st.text_area(
            "Essay: perpetual beta",
            placeholder="I improve this project weekly with feedback...",
            height=90,
        )

        st.subheader("Video / Parser Signals")
        signal_col1, signal_col2, signal_col3 = st.columns(3)
        with signal_col1:
            transcript_available = st.checkbox("Transcript available", value=True)
            q5_level = st.selectbox("Q5 leadership coverage", options=["none", "partial", "full"], index=2)
        with signal_col2:
            mastery_count = int(st.number_input("Mastery mentions", min_value=0, max_value=10, value=2, step=1))
            autonomy_count = int(st.number_input("Autonomy mentions", min_value=0, max_value=10, value=2, step=1))
        with signal_col3:
            mission_count = int(st.number_input("Mission signals", min_value=0, max_value=10, value=3, step=1))
            coverage_ratio = float(st.slider("Coverage ratio", min_value=0.0, max_value=1.0, value=0.7, step=0.05))

        extra_json = st.text_area(
            "Extra JSON merge (optional)",
            placeholder='{"form_data": {"custom_field": "value"}}',
            height=100,
        )
        submitted = st.form_submit_button("Run Scoring", use_container_width=True)

    if submitted:
        payload = _build_payload(
            activities_text=activities_text.strip(),
            honors_text=honors_text.strip(),
            essay_failure=essay_failure.strip(),
            essay_beta=essay_beta.strip(),
            transcript_available=transcript_available,
            q5_level=q5_level,
            coverage_ratio=coverage_ratio,
            mastery_count=mastery_count,
            autonomy_count=autonomy_count,
            mission_count=mission_count,
        )

        if extra_json.strip():
            try:
                parsed_extra = json.loads(extra_json)
                if isinstance(parsed_extra, dict):
                    payload.update(parsed_extra)
                else:
                    st.warning("Extra JSON must be a JSON object.")
            except json.JSONDecodeError as exc:
                st.error(f"Invalid extra JSON: {exc}")

        ok, result = call_evaluate(
            st.session_state["api_base_url"],
            st.session_state["scoring_prefix"],
            payload,
        )
        if ok:
            st.success("Scoring completed.")
            st.session_state["last_scoring_result"] = result
        else:
            st.error("Scoring request failed.")
            st.session_state["last_scoring_result"] = {"error": result}

with right_col:
    st.subheader("Result Summary")
    result = st.session_state["last_scoring_result"]
    if not result:
        st.info("No scoring result yet.")
    else:
        data = result.get("data", {}) if isinstance(result, dict) else {}
        scores = data.get("scores", {}) if isinstance(data, dict) else {}

        st.metric("Final Score", data.get("final_score", "-"))
        st.metric("Bucket", data.get("bucket", "-"))

        for metric_name in ("leadership", "experience", "motivation", "growth", "authenticity"):
            if metric_name in scores:
                st.metric(metric_name.title(), scores.get(metric_name))

        green_flags = data.get("green_flags", [])
        red_flags = data.get("red_flags", [])
        st.markdown("**Green Flags**")
        if isinstance(green_flags, list) and green_flags:
            for item in green_flags:
                st.success(str(item))
        else:
            st.caption("No green flags.")

        st.markdown("**Red Flags**")
        if isinstance(red_flags, list) and red_flags:
            for item in red_flags:
                st.error(str(item))
        else:
            st.caption("No red flags.")

st.markdown("---")
if st.session_state["last_scoring_result"]:
    full = st.session_state["last_scoring_result"]
    breakdown = {}
    if isinstance(full, dict):
        breakdown = full.get("data", {}).get("block_breakdown", {})
    if isinstance(breakdown, dict) and breakdown:
        st.subheader("Block Breakdown")
        st.json(breakdown)
    with st.expander("Raw Response", expanded=bool(st.session_state["show_raw_payloads"])):
        st.json(full)

