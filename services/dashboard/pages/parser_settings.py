from __future__ import annotations

import httpx
import streamlit as st

from core.dashboard_config import ensure_session_settings, load_dashboard_settings

st.set_page_config(
    page_title="Parser Settings",
    page_icon=":mag:",
    layout="wide",
)

ensure_session_settings(st.session_state, load_dashboard_settings())


def call_parser(base_url: str, prefix: str, payload: dict) -> tuple[bool, dict | str]:
    url = f"{base_url.rstrip('/')}/{prefix.strip('/')}/parse"
    try:
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(url, json=payload)
        if resp.status_code >= 400:
            try:
                return False, resp.json()
            except Exception:
                return False, resp.text
        return True, resp.json() if resp.content else {}
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


if "last_parser_response" not in st.session_state:
    st.session_state["last_parser_response"] = {}

st.title("Parser Settings")
st.caption("Run parser tasks in direct mode for GitHub, PDF, and YouTube.")

with st.sidebar:
    st.subheader("Parser API")
    st.session_state["api_base_url"] = st.text_input(
        "API Base URL",
        value=str(st.session_state["api_base_url"]),
    ).strip() or "http://localhost:8000"
    st.session_state["parser_prefix"] = st.text_input(
        "Parser Prefix",
        value=str(st.session_state["parser_prefix"]),
    ).strip() or "parser-service"

left_col, right_col = st.columns([2, 1])

with left_col:
    st.subheader("Run Parse")
    with st.form("parser_form"):
        user_id = st.text_input("user_id", placeholder="candidate_001")
        file_id = st.text_input("file_id (optional)", placeholder="resume_001")
        github_url = st.text_input(
            "github_url (optional)",
            placeholder="https://github.com/username",
        )
        youtube_url = st.text_input(
            "youtube_url (optional)",
            placeholder="https://www.youtube.com/watch?v=...",
        )
        submitted = st.form_submit_button("Start Parsing", use_container_width=True)

    if submitted:
        payload = {"user_id": user_id.strip()}
        if file_id.strip():
            payload["file_id"] = file_id.strip()
        if github_url.strip():
            payload["github_url"] = github_url.strip()
        if youtube_url.strip():
            payload["youtube_url"] = youtube_url.strip()

        if not payload.get("user_id"):
            st.error("user_id is required.")
        elif not any(payload.get(key) for key in ("file_id", "github_url", "youtube_url")):
            st.error("Provide at least one of: file_id, github_url, youtube_url.")
        else:
            ok, result = call_parser(
                st.session_state["api_base_url"],
                st.session_state["parser_prefix"],
                payload,
            )
            if ok and isinstance(result, dict):
                st.session_state["last_parser_response"] = result
                summary = result.get("summary", {})
                success_count = int(summary.get("success_count", 0))
                failure_count = int(summary.get("failure_count", 0))
                st.success("Parser run completed.")
                metric1, metric2 = st.columns(2)
                with metric1:
                    st.metric("Success Tasks", success_count)
                with metric2:
                    st.metric("Failed Tasks", failure_count)
            elif ok:
                st.success("Parser run completed.")
                st.session_state["last_parser_response"] = {"raw_response": result}
            else:
                st.error("Parser request failed.")
                st.session_state["last_parser_response"] = {"error": result}

with right_col:
    st.subheader("Last Result")
    last = st.session_state["last_parser_response"]
    if not last:
        st.info("No parser run yet.")
    else:
        if isinstance(last, dict):
            mode = last.get("mode")
            status = last.get("status")
            if mode:
                st.caption(f"mode: {mode}")
            if status:
                st.caption(f"status: {status}")
            if isinstance(last.get("results"), dict):
                for task_name, task_payload in last["results"].items():
                    task_status = str(task_payload.get("status", "unknown"))
                    if task_status == "SUCCESS":
                        st.success(f"{task_name}: {task_status}")
                    else:
                        st.error(f"{task_name}: {task_status}")
        st.json(last)

st.markdown("---")
st.caption("Parser is configured in direct mode. No queued task_id tracking is required.")

