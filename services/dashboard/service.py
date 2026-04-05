import streamlit as st
import requests
from core.config import SERVICES
st.set_page_config(
    page_title="Juldyz - Ynot Devs",
    layout="wide",
    page_icon="🎓"
)


# Настройки страницы
st.set_page_config(page_title="Juldyz - Ynot Devs", layout="wide", page_icon="🎓")

st.title("Интеллектуальная система отбора - JULDYZ")
st.markdown("Платформа для оценки кандидатов с помощью гибридной AI-системы и парсинга. (Explainable AI)")

