import json
from pathlib import Path
from uuid import uuid4

import streamlit as st

st.set_page_config(
    page_title="Grading Criteria",
    page_icon=":triangular_ruler:",
    layout="wide",
)

ROOT = Path(__file__).resolve().parents[3]
STORE_DIR = ROOT / "data" / "dashboard"
STORE_PATH = STORE_DIR / "grading_criteria.json"

DEFAULT_CRITERIA = [
    {"id": "leadership", "name": "Leadership", "weight": 25, "description": "Инициативность и влияние", "enabled": True},
    {"id": "experience", "name": "Experience", "weight": 25, "description": "Практический опыт и проекты", "enabled": True},
    {"id": "motivation", "name": "Motivation", "weight": 25, "description": "Мотивация и цели", "enabled": True},
    {"id": "authenticity", "name": "Authenticity", "weight": 25, "description": "Аутентичность ответов", "enabled": True},
]


def _load_criteria() -> list[dict]:
    if not STORE_PATH.exists():
        return DEFAULT_CRITERIA.copy()
    try:
        raw = STORE_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return DEFAULT_CRITERIA.copy()


def _save_criteria(items: list[dict]) -> tuple[bool, str]:
    try:
        STORE_DIR.mkdir(parents=True, exist_ok=True)
        STORE_PATH.write_text(
            json.dumps(items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True, "saved"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


if "criteria" not in st.session_state:
    st.session_state.criteria = _load_criteria()

st.title("Grading Criteria")
st.caption("Настройка критериев и их весов для демо-оценки.")

total_weight = sum(int(item.get("weight", 0)) for item in st.session_state.criteria if item.get("enabled", True))
status_col1, status_col2 = st.columns(2)
with status_col1:
    st.metric("Enabled Weight Sum", total_weight)
with status_col2:
    st.metric("Criteria Count", len(st.session_state.criteria))

if total_weight != 100:
    st.warning("Сумма весов активных критериев должна быть 100.")
else:
    st.success("Сумма весов корректна (100).")

st.markdown("---")
st.subheader("Add New Criterion")
with st.form("add_criterion_form"):
    name = st.text_input("Name", placeholder="Communication")
    weight = st.number_input("Weight", min_value=0, max_value=100, value=10, step=1)
    description = st.text_area("Description", placeholder="Короткое пояснение критерия")
    enabled = st.checkbox("Enabled", value=True)
    add_clicked = st.form_submit_button("Add Criterion", use_container_width=True)

if add_clicked:
    if not name.strip():
        st.error("Name обязателен.")
    else:
        st.session_state.criteria.append(
            {
                "id": f"custom_{uuid4().hex[:8]}",
                "name": name.strip(),
                "weight": int(weight),
                "description": description.strip(),
                "enabled": bool(enabled),
            }
        )
        st.success("Критерий добавлен.")

st.markdown("---")
st.subheader("Criteria List")

to_delete_id = None
for idx, item in enumerate(st.session_state.criteria):
    with st.expander(f"{idx + 1}. {item.get('name', 'Unnamed')}"):
        c1, c2 = st.columns([3, 1])
        with c1:
            item["name"] = st.text_input("Name", value=item.get("name", ""), key=f"name_{item['id']}")
            item["description"] = st.text_area(
                "Description",
                value=item.get("description", ""),
                key=f"desc_{item['id']}",
                height=80,
            )
        with c2:
            item["weight"] = int(
                st.number_input(
                    "Weight",
                    min_value=0,
                    max_value=100,
                    value=int(item.get("weight", 0)),
                    step=1,
                    key=f"weight_{item['id']}",
                )
            )
            item["enabled"] = st.checkbox("Enabled", value=bool(item.get("enabled", True)), key=f"enabled_{item['id']}")
            if st.button("Delete", key=f"del_{item['id']}", use_container_width=True):
                to_delete_id = item["id"]

if to_delete_id:
    st.session_state.criteria = [x for x in st.session_state.criteria if x.get("id") != to_delete_id]
    st.warning("Критерий удален.")

st.markdown("---")
action_col1, action_col2, action_col3 = st.columns(3)
with action_col1:
    if st.button("Save to JSON", use_container_width=True):
        ok, msg = _save_criteria(st.session_state.criteria)
        if ok:
            st.success(f"Сохранено: {STORE_PATH}")
        else:
            st.error(f"Ошибка сохранения: {msg}")
with action_col2:
    if st.button("Reload from JSON", use_container_width=True):
        st.session_state.criteria = _load_criteria()
        st.info("Загружено из файла.")
with action_col3:
    if st.button("Reset Defaults", use_container_width=True):
        st.session_state.criteria = DEFAULT_CRITERIA.copy()
        st.info("Сброшено к дефолтным критериям.")
