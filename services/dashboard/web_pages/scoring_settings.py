import json
import os

import httpx
import streamlit as st

DEFAULT_API_BASE_URL = os.getenv("JULDYZ_API_BASE_URL", "http://localhost:8000")
DEFAULT_SCORING_PREFIX = os.getenv("JULDYZ_SCORING_PREFIX", "scoring-service")

st.set_page_config(
    page_title="Scoring Settings",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
)


def call_evaluate(base_url: str, prefix: str, payload: dict) -> tuple[bool, dict | str]:
    url = f"{base_url.rstrip('/')}/{prefix.strip('/')}/evaluate"
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(url, json=payload)
        if resp.status_code >= 400:
            try:
                data = resp.json()
            except Exception:
                data = resp.text
            return False, data
        return True, resp.json() if resp.content else {}
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


if "api_base_url" not in st.session_state:
    st.session_state.api_base_url = DEFAULT_API_BASE_URL
if "scoring_prefix" not in st.session_state:
    st.session_state.scoring_prefix = DEFAULT_SCORING_PREFIX
if "last_scoring_result" not in st.session_state:
    st.session_state.last_scoring_result = {}

st.title("Scoring Settings")
st.caption("Запуск оценки кандидата и просмотр explainable-результатов.")

with st.sidebar:
    st.subheader("Scoring API")
    st.session_state.api_base_url = st.text_input(
        "API Base URL",
        value=st.session_state.api_base_url,
        help="Обычно http://localhost:8000 для gateway",
    ).strip() or DEFAULT_API_BASE_URL
    st.session_state.scoring_prefix = st.text_input(
        "Scoring Prefix",
        value=st.session_state.scoring_prefix,
        help="Обычно scoring-service",
    ).strip() or DEFAULT_SCORING_PREFIX

left_col, right_col = st.columns([2, 1])

with left_col:
    st.subheader("Candidate Input")
    with st.form("score_form"):
        candidate_id = st.text_input("candidate_id", placeholder="candidate_001")
        essay = st.text_area(
            "essay",
            placeholder="Кандидат рассказывает про проекты, мотивацию и цели...",
            height=180,
        )
        commits = st.number_input("github_stats.total_commits", min_value=0, value=0, step=1)
        repo_count = st.number_input("github_stats.repo_count", min_value=0, value=0, step=1)
        extra_json = st.text_area(
            "extra JSON (optional)",
            placeholder='{"form_data": {"city": "Almaty"}}',
            height=100,
        )
        submitted = st.form_submit_button("Run Scoring", use_container_width=True)

    if submitted:
        payload = {
            "candidate_id": candidate_id.strip(),
            "essay": essay.strip(),
            "github_stats": {
                "total_commits": int(commits),
                "repo_count": int(repo_count),
            },
        }

        if extra_json.strip():
            try:
                extra = json.loads(extra_json)
                if isinstance(extra, dict):
                    payload.update(extra)
                else:
                    st.warning("extra JSON должен быть объектом.")
            except json.JSONDecodeError as exc:
                st.error(f"Некорректный JSON в extra: {exc}")

        ok, result = call_evaluate(
            st.session_state.api_base_url,
            st.session_state.scoring_prefix,
            payload,
        )
        if ok:
            st.success("Scoring завершен.")
            st.session_state.last_scoring_result = result if isinstance(result, dict) else {}
            st.json(result)
        else:
            st.error("Ошибка при вызове scoring.")
            st.json(result)

with right_col:
    st.subheader("Summary")
    result = st.session_state.last_scoring_result
    if not isinstance(result, dict) or not result:
        st.info("Пока нет результата. Запусти scoring слева.")
    else:
        data = result.get("data", {}) if isinstance(result.get("data"), dict) else {}
        scores = data.get("scores", {}) if isinstance(data.get("scores"), dict) else {}
        overall = data.get("overall_score")

        if overall is not None:
            st.metric("Overall Score", overall)

        for key in ["leadership", "experience", "motivation", "authenticity"]:
            if key in scores:
                st.metric(key.title(), scores[key])

        red_flags = data.get("red_flags", [])
        green_flags = data.get("green_flags", [])

        st.markdown("**Green Flags**")
        if isinstance(green_flags, list) and any(str(x).strip() for x in green_flags):
            for item in green_flags:
                if str(item).strip():
                    st.success(str(item))
        else:
            st.caption("Нет данных.")

        st.markdown("**Red Flags**")
        if isinstance(red_flags, list) and any(str(x).strip() for x in red_flags):
            for item in red_flags:
                if str(item).strip():
                    st.error(str(item))
        else:
            st.caption("Нет данных.")
