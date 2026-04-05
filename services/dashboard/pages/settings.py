from __future__ import annotations

import streamlit as st

from core.dashboard_config import (
    DEFAULT_SETTINGS,
    SETTINGS_PATH,
    build_settings_from_session,
    ensure_session_settings,
    load_dashboard_settings,
    save_dashboard_settings,
)

st.set_page_config(
    page_title="Dashboard Settings",
    page_icon=":gear:",
    layout="wide",
)

settings = load_dashboard_settings()
ensure_session_settings(st.session_state, settings)

st.title("Settings")
st.caption("Global dashboard settings used by all pages.")

with st.sidebar:
    st.subheader("Actions")
    if st.button("Reload from File", use_container_width=True):
        file_settings = load_dashboard_settings()
        st.session_state["api_base_url"] = file_settings["api_base_url"]
        st.session_state["form_prefix"] = file_settings["prefixes"]["form"]
        st.session_state["parser_prefix"] = file_settings["prefixes"]["parser"]
        st.session_state["scoring_prefix"] = file_settings["prefixes"]["scoring"]
        st.session_state["llm_prefix"] = file_settings["prefixes"]["llm"]
        st.session_state["bot_prefix"] = file_settings["prefixes"]["bot"]
        st.session_state["dashboard_prefix"] = file_settings["prefixes"]["dashboard"]
        st.session_state["candidate_page_size"] = file_settings["ui"]["candidate_page_size"]
        st.session_state["show_raw_payloads"] = file_settings["ui"]["show_raw_payloads"]
        st.success("Loaded settings from file.")

    if st.button("Reset to Defaults", use_container_width=True):
        defaults = DEFAULT_SETTINGS
        st.session_state["api_base_url"] = defaults["api_base_url"]
        st.session_state["form_prefix"] = defaults["prefixes"]["form"]
        st.session_state["parser_prefix"] = defaults["prefixes"]["parser"]
        st.session_state["scoring_prefix"] = defaults["prefixes"]["scoring"]
        st.session_state["llm_prefix"] = defaults["prefixes"]["llm"]
        st.session_state["bot_prefix"] = defaults["prefixes"]["bot"]
        st.session_state["dashboard_prefix"] = defaults["prefixes"]["dashboard"]
        st.session_state["candidate_page_size"] = defaults["ui"]["candidate_page_size"]
        st.session_state["show_raw_payloads"] = defaults["ui"]["show_raw_payloads"]
        st.info("Session reset to default values.")

st.subheader("Backend")
backend_col1, backend_col2 = st.columns(2)
with backend_col1:
    st.session_state["api_base_url"] = st.text_input(
        "API Base URL",
        value=str(st.session_state["api_base_url"]),
        help="Gateway URL, usually http://localhost:8000",
    ).strip() or DEFAULT_SETTINGS["api_base_url"]

with backend_col2:
    st.session_state["candidate_page_size"] = int(
        st.number_input(
            "Candidates Page Size",
            min_value=10,
            max_value=500,
            value=int(st.session_state["candidate_page_size"]),
            step=10,
        )
    )

st.subheader("Service Prefixes")
prefix_col1, prefix_col2, prefix_col3 = st.columns(3)

with prefix_col1:
    st.session_state["form_prefix"] = st.text_input(
        "Form Prefix",
        value=str(st.session_state["form_prefix"]),
    ).strip() or DEFAULT_SETTINGS["prefixes"]["form"]
    st.session_state["parser_prefix"] = st.text_input(
        "Parser Prefix",
        value=str(st.session_state["parser_prefix"]),
    ).strip() or DEFAULT_SETTINGS["prefixes"]["parser"]

with prefix_col2:
    st.session_state["scoring_prefix"] = st.text_input(
        "Scoring Prefix",
        value=str(st.session_state["scoring_prefix"]),
    ).strip() or DEFAULT_SETTINGS["prefixes"]["scoring"]
    st.session_state["llm_prefix"] = st.text_input(
        "LLM Prefix",
        value=str(st.session_state["llm_prefix"]),
    ).strip() or DEFAULT_SETTINGS["prefixes"]["llm"]

with prefix_col3:
    st.session_state["bot_prefix"] = st.text_input(
        "Bot Prefix",
        value=str(st.session_state["bot_prefix"]),
    ).strip() or DEFAULT_SETTINGS["prefixes"]["bot"]
    st.session_state["dashboard_prefix"] = st.text_input(
        "Dashboard Prefix",
        value=str(st.session_state["dashboard_prefix"]),
    ).strip() or DEFAULT_SETTINGS["prefixes"]["dashboard"]

st.subheader("UI")
st.session_state["show_raw_payloads"] = st.checkbox(
    "Show raw payloads by default",
    value=bool(st.session_state["show_raw_payloads"]),
)

st.markdown("---")
save_col1, save_col2 = st.columns(2)
with save_col1:
    if st.button("Save Settings", use_container_width=True):
        ok, result = save_dashboard_settings(build_settings_from_session(st.session_state))
        if ok:
            st.success(f"Saved to {result}")
        else:
            st.error(result)

with save_col2:
    if st.button("Preview JSON", use_container_width=True):
        st.json(build_settings_from_session(st.session_state))

st.caption(f"Settings file: {SETTINGS_PATH}")

