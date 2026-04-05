from __future__ import annotations

from datetime import datetime, timezone

import httpx
import streamlit as st

from core.dashboard_config import ensure_session_settings, load_dashboard_settings

st.set_page_config(
    page_title="Health",
    page_icon=":stethoscope:",
    layout="wide",
)

ensure_session_settings(st.session_state, load_dashboard_settings())


def _get_json(url: str, timeout: float = 4.0) -> tuple[bool, dict | str]:
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
        if resp.status_code >= 400:
            return False, f"HTTP {resp.status_code}"
        if not resp.content:
            return True, {}
        try:
            return True, resp.json()
        except Exception:
            return False, "Non-JSON response"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _service_health(base_url: str, prefix: str) -> tuple[bool, str]:
    ok, payload = _get_json(f"{base_url}/{prefix}/health")
    if not ok:
        return False, str(payload)
    if isinstance(payload, dict):
        status = str(payload.get("status", "unknown"))
        return status == "ok", f"status={status}"
    return False, "invalid payload"


st.title("Health")
st.caption("Gateway + service level checks.")

with st.sidebar:
    st.subheader("Target")
    st.session_state["api_base_url"] = st.text_input(
        "API Base URL",
        value=str(st.session_state["api_base_url"]),
    ).strip() or "http://localhost:8000"
    if st.button("Refresh", use_container_width=True):
        st.rerun()

base_url = st.session_state["api_base_url"].rstrip("/")
now_utc = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

gateway_ok, gateway_payload = _get_json(f"{base_url}/health")

metric1, metric2, metric3, metric4 = st.columns(4)
with metric1:
    st.metric("Gateway", "online" if gateway_ok else "offline")
with metric2:
    if gateway_ok and isinstance(gateway_payload, dict):
        services = gateway_payload.get("services", [])
        total = len(services)
        running = sum(1 for item in services if item.get("running"))
        st.metric("Services Running", f"{running}/{total}")
    else:
        st.metric("Services Running", "-")
with metric3:
    st.metric("API URL", base_url)
with metric4:
    st.metric("Last Check", now_utc)

left_col, right_col = st.columns([2, 1])
with left_col:
    st.subheader("Gateway Health")
    if gateway_ok and isinstance(gateway_payload, dict):
        st.success("Gateway is reachable.")
        st.json(gateway_payload)
    else:
        st.error(f"Gateway check failed: {gateway_payload}")

with right_col:
    st.subheader("Service Quick Check")
    prefixes = [
        st.session_state["form_prefix"],
        st.session_state["parser_prefix"],
        st.session_state["scoring_prefix"],
        st.session_state["llm_prefix"],
        st.session_state["bot_prefix"],
        st.session_state["dashboard_prefix"],
    ]
    for prefix in prefixes:
        ok, detail = _service_health(base_url, prefix)
        if ok:
            st.success(f"{prefix}: ok")
        else:
            st.warning(f"{prefix}: {detail}")

