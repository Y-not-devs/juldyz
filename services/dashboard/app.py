import streamlit as st
import requests
from core.logger import setup_logging
setup_logging("dashboard")

SCORING_API_URL = "http://127.0.0.1:8003/evaluate"

# Настройки страницы
st.set_page_config(page_title="inVision U - Приемная комиссия", layout="wide", page_icon="🎓")

st.title("Интеллектуальная система отбора - inVision U")
st.markdown("Платформа для оценки кандидатов с помощью гибридной AI-системы и парсинга GitHub. (Explainable AI)")

# Боковая панель для ввода данных кандидата
with st.sidebar:
    st.header("Данные кандидата")
    name = st.text_input("ФИО", "Айгерим")
    age = st.number_input("Возраст", min_value=14, max_value=30, value=17)
    essay = st.text_area("Эссе / Мотивационное письмо", "В современном мире важно быть лидером. Я создала стартап, который помогает школьникам готовиться к ЕНТ.", height=200)
    github_commits = st.number_input("Данные парсера: GitHub коммиты", min_value=0, value=150)
    
    st.markdown("---")
    submit_btn = st.button("Оценить кандидата", type="primary", use_container_width=True)

# Основная область экрана
if submit_btn:
    payload = {
        "name": name,
        "age": age,
        "essay": essay,
        "github_stats": {
            "total_commits": github_commits
        }
    }
    
    with st.spinner("Идет глубокий анализ профиля кандидата силами AI..."):
        try:
            # Делаем запрос к нашему сервису скоринга
            response = requests.post(SCORING_API_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "success":
                result = data["data"]
                scores = result.get("scores", {})
                
                # Показываем имя и итоговый балл
                st.header(f"Кандидат: {name} ({age} лет)")
                st.subheader(f"🏆 Итоговый AI-скор: {result.get('overall_score')}/10")
                
                st.markdown("### 📊 Детализация оценки")
                # Красивые колонки с метриками
                col1, col2, col3, col4 = st.columns(4)
                col1.metric(label="Лидерство", value=f"{scores.get('leadership', 0)}/10")
                col2.metric(label="Опыт (Hard Skills)", value=f"{scores.get('experience', 0)}/10")
                col3.metric(label="Мотивация", value=f"{scores.get('motivation', 0)}/10")
                col4.metric(label="Аутентичность (Анти-GPT)", value=f"{scores.get('authenticity', 0)}/10")
                
                st.divider()
                
                # Текстовое обоснование - ключевой пункт для хакатона (Explainable AI)
                st.subheader("Анализ ИИ (Explainability)")
                st.info(result.get("explanation", "Нет данных"))
                
                # Красные и зеленые флаги
                col_flags1, col_flags2 = st.columns(2)
                with col_flags1:
                    st.subheader("✅ Зеленые флаги")
                    for gf in result.get("green_flags", []):
                        if gf: 
                            st.success(f"**+** {gf}")
                with col_flags2:
                    st.subheader("Красные флаги (Зоны риска)")
                    red_flags = [rf for rf in result.get("red_flags", []) if rf]
                    if red_flags:
                        for rf in red_flags:
                            st.error(f"**-** {rf}")
                    else:
                        st.markdown("_Рисков не выявлено_")
            else:
                st.error(f"Ошибка бэкенда: {data.get('detail')}")
                
        except requests.exceptions.ConnectionError:
            st.error("Ошибка соединения! Убедитесь, что Scoring Service запущен на порту 8003.")
        except Exception as e:
            st.error(f"Произошла ошибка: {e}")
else:
    # Заглушка, пока кнопка не нажата
    st.info("Введите данные кандидата в панели слева и нажмите 'Оценить кандидата'.")