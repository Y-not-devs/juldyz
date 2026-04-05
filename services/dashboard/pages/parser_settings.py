import os

import httpx
import streamlit as st

DEFAULT_API_BASE_URL = os.getenv("JULDYZ_API_BASE_URL", "http://localhost:8000")
DEFAULT_PARSER_PREFIX = os.getenv("JULDYZ_PARSER_PREFIX", "parser-service")

st.set_page_config(
    page_title="Parser Settings",
    page_icon=":mag_right:",
    layout="wide",
)


def post_parse(base_url: str, prefix: str, payload: dict) -> tuple[bool, dict | str]:
    url = f"{base_url.rstrip('/')}/{prefix.strip('/')}/parse"
    try:
        with httpx.Client(timeout=10.0) as client:
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


def get_task_status(base_url: str, prefix: str, task_id: str) -> tuple[bool, dict | str]:
    url = f"{base_url.rstrip('/')}/{prefix.strip('/')}/parse/tasks/{task_id}"
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(url)
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
if "parser_prefix" not in st.session_state:
    st.session_state.parser_prefix = DEFAULT_PARSER_PREFIX
if "last_parser_response" not in st.session_state:
    st.session_state.last_parser_response = {}

st.title("Parser Settings")
st.caption("Запуск задач парсинга по GitHub и/или PDF (file_id).")

with st.sidebar:
    st.subheader("Parser API")
    st.session_state.api_base_url = st.text_input(
        "API Base URL",
        value=st.session_state.api_base_url,
        help="Обычно http://localhost:8000 для gateway",
    ).strip() or DEFAULT_API_BASE_URL
    st.session_state.parser_prefix = st.text_input(
        "Parser Prefix",
        value=st.session_state.parser_prefix,
        help="Обычно parser-service",
    ).strip() or DEFAULT_PARSER_PREFIX

left_col, right_col = st.columns([2, 1])

with left_col:
    st.subheader("Run Parse")
    with st.form("parse_form"):
        user_id = st.text_input("user_id", placeholder="candidate_001")
        file_id = st.text_input("file_id (optional)", placeholder="resume_001")
        github_url = st.text_input(
            "github_url (optional)",
            placeholder="https://github.com/username",
        )
        submitted = st.form_submit_button("Start Parsing", use_container_width=True)

    if submitted:
        payload = {"user_id": user_id.strip()}
        if file_id.strip():
            payload["file_id"] = file_id.strip()
        if github_url.strip():
            payload["github_url"] = github_url.strip()

        if not payload.get("user_id"):
            st.error("Поле user_id обязательно.")
        elif not payload.get("file_id") and not payload.get("github_url"):
            st.error("Укажи хотя бы file_id или github_url.")
        else:
            ok, result = post_parse(
                st.session_state.api_base_url,
                st.session_state.parser_prefix,
                payload,
            )
            if ok:
                st.success("Задачи парсинга отправлены.")
                st.session_state.last_parser_response = result if isinstance(result, dict) else {}
                st.json(result)
            else:
                st.error("Ошибка при запуске parser.")
                st.json(result)

with right_col:
    st.subheader("Track Task")

    default_task_id = ""
    last = st.session_state.last_parser_response
    if isinstance(last, dict):
        default_task_id = (
            last.get("github_task_id")
            or last.get("file_task_id")
            or ""
        )

    task_id = st.text_input("task_id", value=default_task_id)
    if st.button("Check Status", use_container_width=True):
        if not task_id.strip():
            st.warning("Введи task_id.")
        else:
            ok, result = get_task_status(
                st.session_state.api_base_url,
                st.session_state.parser_prefix,
                task_id.strip(),
            )
            if ok:
                status = result.get("status", "unknown") if isinstance(result, dict) else "unknown"
                if status in {"SUCCESS"}:
                    st.success(f"Task status: {status}")
                elif status in {"FAILURE"}:
                    st.error(f"Task status: {status}")
                else:
                    st.info(f"Task status: {status}")
                st.json(result)
            else:
                st.error("Не удалось получить статус задачи.")
                st.json(result)
