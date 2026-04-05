import os
from datetime import datetime, timezone

import httpx
import streamlit as st

DEFAULT_API_BASE_URL = os.getenv("JULDYZ_API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Juldyz Dashboard Overview",
    page_icon=":clipboard:",
    layout="wide",
)


def _get_json(url: str, timeout: float = 4.0) -> tuple[bool, dict | str]:
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}"
        return True, resp.json() if resp.content else {}
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _service_health(base_url: str, prefix: str) -> tuple[bool, str]:
    ok, payload = _get_json(f"{base_url.rstrip('/')}/{prefix}/health")
    if not ok:
        return False, str(payload)
    status = str(payload.get("status", "unknown")) if isinstance(payload, dict) else "unknown"
    return status == "ok", f"status={status}"


if "api_base_url" not in st.session_state:
    st.session_state.api_base_url = DEFAULT_API_BASE_URL

st.title("Dashboard Overview")
st.caption("Обзор состояния системы и быстрые проверки ключевых API.")

with st.sidebar:
    st.subheader("Backend")
    api_base_url = st.text_input("API Base URL", value=st.session_state.api_base_url).strip()
    st.session_state.api_base_url = api_base_url or DEFAULT_API_BASE_URL

    if st.button("Обновить статус", use_container_width=True):
        st.rerun()

base_url = st.session_state.api_base_url.rstrip("/")
now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

gateway_ok, gateway_payload = _get_json(f"{base_url}/health")

metric_1, metric_2, metric_3, metric_4 = st.columns(4)
with metric_1:
    st.metric("Gateway", "online" if gateway_ok else "offline")
with metric_2:
    running = 0
    total = 0
    if gateway_ok and isinstance(gateway_payload, dict):
        services = gateway_payload.get("services", [])
        total = len(services)
        running = sum(1 for svc in services if svc.get("running"))
    st.metric("Services Running", f"{running}/{total}" if total else "-")
with metric_3:
    st.metric("API URL", base_url)
with metric_4:
    st.metric("Last Check (UTC)", now_utc.split(" ")[1])

st.markdown("---")

left_col, right_col = st.columns([2, 1])

with left_col:
    st.subheader("Gateway Health")
    if gateway_ok:
        st.success("Gateway отвечает.")
        if isinstance(gateway_payload, dict):
            st.json(gateway_payload)
    else:
        st.error(f"Gateway недоступен: {gateway_payload}")

with right_col:
    st.subheader("Service Quick Check")
    prefixes = [
        "form-service",
        "parser-service",
        "scoring-service",
        "llm-service",
        "bot-service",
        "dashboard-service",
    ]
    for prefix in prefixes:
        ok, details = _service_health(base_url, prefix)
        if ok:
            st.success(f"{prefix}: ok")
        else:
            st.warning(f"{prefix}: {details}")

st.markdown("---")
st.subheader("Quick Actions")
action_col1, action_col2, action_col3 = st.columns(3)

with action_col1:
    if st.button("Ping Form /form-submit", use_container_width=True):
        st.info("Форма требует POST payload, проверка доступности делается через /form-service/health.")
with action_col2:
    if st.button("Ping Parser /parse", use_container_width=True):
        st.info("Parser требует POST payload, базовый статус смотри через /parser-service/health.")
with action_col3:
    if st.button("Ping Scoring /evaluate", use_container_width=True):
        st.info("Scoring требует POST payload, базовый статус смотри через /scoring-service/health.")
