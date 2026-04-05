import os
from datetime import datetime, timezone

import httpx
import streamlit as st

DEFAULT_API_BASE_URL = os.getenv("JULDYZ_API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Juldyz Dashboard",
    page_icon=":bar_chart:",
    layout="wide",
)


def check_api_health(base_url: str) -> tuple[bool, str]:
    health_url = f"{base_url.rstrip('/')}/health"
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(health_url)
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}"

        payload = resp.json() if resp.content else {}

        # Gateway format: {"gateway": "ok", ...}
        if str(payload.get("gateway", "")).lower() == "ok":
            return True, "gateway=ok"

        # Service format: {"status": "ok", ...}
        status = str(payload.get("status", "unknown"))
        return status.lower() == "ok", f"status={status}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


st.title("Juldyz Dashboard")
st.caption(
    "Dashboard для демо: парсинг, скоринг и explainable-сигналы по кандидатам."
)

if "api_base_url" not in st.session_state:
    st.session_state.api_base_url = DEFAULT_API_BASE_URL

with st.sidebar:
    st.subheader("Backend")
    api_base_url = st.text_input(
        "API Base URL",
        value=st.session_state.api_base_url,
        help="Например: http://localhost:8000",
    ).strip()
    st.session_state.api_base_url = api_base_url or DEFAULT_API_BASE_URL

    if st.button("Проверить /health", use_container_width=True):
        ok, details = check_api_health(st.session_state.api_base_url)
        if ok:
            st.success(f"API доступен: {details}")
        else:
            st.error(f"API недоступен: {details}")

    st.markdown("---")
    st.subheader("Страницы")
    st.markdown("- `dashboard.py`")
    st.markdown("- `parser_settings.py`")
    st.markdown("- `scoring_settings.py`")
    st.markdown("- `grading_criteria.py`")
    st.markdown("- `candidates_list.py`")
    st.markdown("- `form_settings.py`")
    st.markdown("- `llm_settings.py`")
    st.markdown("- `bot_settings.py`")

left_col, right_col = st.columns([2, 1])

with left_col:
    st.subheader("Контекст")
    st.write(
        "Juldyz помогает комиссии оценивать не только текущие достижения,"
        " но и траекторию роста кандидата."
    )

    st.subheader("Текущий фокус")
    st.markdown("1. Собрать работающий end-to-end demo")
    st.markdown("2. Подключить parser/scoring к кнопкам в UI")
    st.markdown("3. Затем улучшать UX и надежность")

with right_col:
    st.subheader("Системный статус")
    ok, details = check_api_health(st.session_state.api_base_url)
    if ok:
        st.success("Backend: online")
    else:
        st.warning("Backend: offline")

    st.code(f"API: {st.session_state.api_base_url}\n/details: {details}", language="text")
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    st.caption(f"Обновлено: {now_utc}")

st.markdown("---")
st.info("Хакатон-режим: одна задача -> одно рабочее решение.")
