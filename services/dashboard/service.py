import streamlit as st

# services/dashboard/service.py

import subprocess
import sys

def run_dashboard():
    subprocess.Popen([
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "services/dashboard/app.py",
        "--server.port=8501",
        "--server.headless=true",
    ])
    
st.set_page_config(
    page_title="inVision U",
    layout="wide",
    page_icon="🎓"
)

st.title("inVision U Dashboard")
st.sidebar.success("Выберите страницу")

st.write("Главная страница")