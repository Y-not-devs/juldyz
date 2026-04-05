from __future__ import annotations

import httpx
import streamlit as st

from core.dashboard_config import ensure_session_settings, load_dashboard_settings

st.set_page_config(
    page_title="Bot Settings",
    page_icon=":speech_balloon:",
    layout="wide",
)

ensure_session_settings(st.session_state, load_dashboard_settings())


def _get_json(url: str, timeout: float = 5.0) -> tuple[bool, dict | str]:
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
        if resp.status_code >= 400:
            return False, f"HTTP {resp.status_code}"
        try:
            return True, resp.json()
        except Exception:
            return False, "Non-JSON response"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _post_json(url: str, payload: dict, timeout: float = 10.0) -> tuple[bool, dict | str]:
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
        if resp.status_code >= 400:
            try:
                return False, resp.json()
            except Exception:
                return False, resp.text
        return True, resp.json() if resp.content else {}
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


st.title("Bot Settings")
st.caption("Notify a candidate via bot-service and validate bot API status.")

with st.sidebar:
    st.subheader("Bot API")
    st.session_state["api_base_url"] = st.text_input(
        "API Base URL",
        value=str(st.session_state["api_base_url"]),
    ).strip() or "http://localhost:8000"
    st.session_state["bot_prefix"] = st.text_input(
        "Bot Prefix",
        value=str(st.session_state["bot_prefix"]),
    ).strip() or "bot-service"

base_url = st.session_state["api_base_url"].rstrip("/")
bot_prefix = st.session_state["bot_prefix"].strip("/")

health_col, notify_col = st.columns([1, 2])
with health_col:
    st.subheader("Health")
    ok, health_payload = _get_json(f"{base_url}/{bot_prefix}/health")
    if ok:
        st.success("bot-service is reachable")
        st.json(health_payload)
    else:
        st.error("bot-service check failed")
        st.code(str(health_payload))

with notify_col:
    st.subheader("Send Notification")
    with st.form("notify_form"):
        tg_id = st.text_input("Telegram ID (tg_id)", placeholder="123456789")
        candidate_id = st.text_input("candidate_id (optional)", placeholder="candidate_001")
        st.caption("Current endpoint sends the default confirmation message.")
        submitted = st.form_submit_button("Send via /notify", use_container_width=True)

    if submitted:
        if not tg_id.strip():
            st.error("tg_id is required.")
        else:
            payload = {"tg_id": tg_id.strip()}
            if candidate_id.strip():
                payload["candidate_id"] = candidate_id.strip()

            ok, response_payload = _post_json(
                f"{base_url}/{bot_prefix}/notify",
                payload=payload,
            )
            if ok:
                st.success("Notification request sent.")
                st.json(response_payload)
            else:
                st.error("Notification request failed.")
                st.json(response_payload)

st.markdown("---")
st.info("Candidate must start the Telegram bot first, otherwise message delivery can fail.")

