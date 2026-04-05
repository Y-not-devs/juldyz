from __future__ import annotations

import streamlit as st

from core.dashboard_config import (
    SETTINGS_PATH,
    ensure_session_settings,
    load_dashboard_settings,
)

st.set_page_config(
    page_title="Juldyz Dashboard",
    layout="wide",
    page_icon=":bar_chart:",
)

settings = load_dashboard_settings()
ensure_session_settings(st.session_state, settings)

st.title("Juldyz Dashboard")
st.caption("Jury workspace for service health checks, parsing, scoring, and candidate review.")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("API Base URL", st.session_state["api_base_url"])
with col2:
    st.metric("Parser Prefix", st.session_state["parser_prefix"])
with col3:
    st.metric("Scoring Prefix", st.session_state["scoring_prefix"])

st.markdown("---")

st.subheader("Quick Start")
st.markdown(
    """
1. Open **Settings** and confirm API URL + service prefixes.
2. Open **Health** and verify all services are online.
3. Open **Parser Settings** to run GitHub/PDF/YouTube parsing.
4. Open **Scoring Settings** to evaluate candidate profiles.
5. Open **Candidates List** to inspect saved records from SQLite.
    """.strip()
)

st.subheader("Storage")
st.code(str(SETTINGS_PATH), language="text")

st.info("All dashboard pages share one settings file and one Streamlit session state.")

