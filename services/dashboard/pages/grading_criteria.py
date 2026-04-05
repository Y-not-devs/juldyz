from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Grading Criteria",
    page_icon=":abacus:",
    layout="wide",
)

WEIGHTS = {"A": 2.0, "B": 3.0, "C": 1.5}
BUCKETS = {
    "A": (8.5, 15.0),
    "B": (5.0, 8.49),
    "C": (0.0, 4.99),
}


def _bucket_for_score(final_score: float) -> str:
    for bucket, (low, high) in BUCKETS.items():
        if low <= final_score <= high:
            return bucket
    return "C"


st.title("Grading Criteria")
st.caption("Методология скоринга кандидата: формула, источники сигналов и интерпретация результата.")

st.subheader("1) Итоговая формула")
st.markdown(
    """
Итог считается как средневзвешенная сумма трёх независимых блоков (A, B, C),
умноженная на контекстный коэффициент `C`:
    """
)
st.latex(r"\text{FinalScore}=\left(\frac{A\cdot W_A + B\cdot W_B + C\cdot W_C}{W_A+W_B+W_C}\right)\cdot C")
st.markdown(
    f"""
- Веса блоков в коде сервиса:
  - `W_A = {WEIGHTS["A"]}`
  - `W_B = {WEIGHTS["B"]}`
  - `W_C = {WEIGHTS["C"]}`
- Сейчас в реализации `context_multiplier = 1.0`.
- Формула и веса соответствуют `services/scoring/service.py`.
    """
)

st.markdown("---")
st.subheader("2) Детализация блоков (0-10 баллов каждый)")

col_a, col_b, col_c = st.columns(3)

with col_a:
    st.markdown("### Блок A: Упорство и Grit (`W=2.0`)")
    st.markdown(
        """
- `duration_commitment (0..4)`:
  - +2 балла за каждое долгосрочное занятие (`2+ years`, `yrs`, `year`)
  - максимум 4.
- `vertical_progress (0..3)`:
  - 3 балла при наличии признаков лидерства:
  `captain`, `president`, `leader`, `mentor`, `elected` и т.д.
- `achievements (0..3)`:
  - 3 балла при наличии достижений:
  `award`, `winner`, `medal`, `published`, `launched` и т.д.
- Итого: `A = min(10, duration + progress + achievements)`.
        """
    )

with col_b:
    st.markdown("### Блок B: Growth Mindset (`W=3.0`)")
    st.markdown(
        """
- `reaction_to_failure (0..5)`:
  - базовая логика оценивает эссе про провал:
  анализ причин + смена стратегии -> рост балла;
  blame/avoidance -> штраф.
- `challenge_orientation (0..5)`:
  - оценивается эссе про `perpetual beta`:
  выбор сложных задач, итеративное улучшение, работа с фидбеком.
- Итого: `B = min(10, reaction_to_failure + challenge_orientation)`.
        """
    )

with col_c:
    st.markdown("### Блок C: Внутренняя мотивация и Drive (`W=1.5`)")
    st.markdown(
        """
- `intrinsic_type_i (0..4)`:
  - сигналы мастерства + автономии из видео/парсера.
- `mission_alignment (0..6)`:
  - количество сигналов миссии/социального вклада.
- Итого: `C = min(10, intrinsic + mission_alignment)`.
- Источник:
  - `parser_signals` если транскрипт доступен;
  - `fallback_no_video` если нет.
        """
    )

st.markdown("---")
st.subheader("3) Откуда берутся сигналы (по полям анкеты и парсера)")

st.markdown(
    """
**Блок A (Common App / анкета):**
- `Activity type`
- `Position/Leadership description`
- `Organization Name`
- `Please describe this activity...`
- `Honors ...`, `Level(s) of recognition`, `award/recognition` поля

**Блок B (эссе):**
- Вопрос про провал и анализ ошибок:
  `Reflect on a situation where your efforts or plan significantly failed...`
- Вопрос про `perpetual beta`:
  `The concept of "perpetual beta" means...`

**Блок C (parser/video):**
- `parser_context.results.video_task.result.analysis.signals.intrinsic`
- `parser_context.results.video_task.result.analysis.signals.mission_alignment`
- `parser_context.results.video_task.result.transcript.available`
    """
)

st.info(
    "Страница описывает текущую реализацию скоринга. "
    "Она не добавляет новые критерии и не меняет формулу."
)

st.markdown("---")
st.subheader("4) Интерпретация итогового балла (Buckets)")
st.markdown(
    f"""
- **Bucket A**: `{BUCKETS["A"][0]} .. {BUCKETS["A"][1]}` -> высокий приоритет.
- **Bucket B**: `{BUCKETS["B"][0]} .. {BUCKETS["B"][1]}` -> потенциал, нужен интервью-чек.
- **Bucket C**: `{BUCKETS["C"][0]} .. {BUCKETS["C"][1]}` -> высокий риск несоответствия.
    """
)

st.markdown("---")
st.subheader("5) Калькулятор по формуле")
st.caption("Для жюри: быстро проверить, как блоки влияют на итог.")

calc_col1, calc_col2 = st.columns([2, 1])
with calc_col1:
    a_score = float(st.slider("A (0..10)", min_value=0.0, max_value=10.0, value=6.0, step=0.1))
    b_score = float(st.slider("B (0..10)", min_value=0.0, max_value=10.0, value=6.0, step=0.1))
    c_score = float(st.slider("C (0..10)", min_value=0.0, max_value=10.0, value=6.0, step=0.1))
    context_multiplier = float(st.slider("Context multiplier C", min_value=0.5, max_value=1.5, value=1.0, step=0.05))

weighted_sum = a_score * WEIGHTS["A"] + b_score * WEIGHTS["B"] + c_score * WEIGHTS["C"]
weighted_avg = round(weighted_sum / sum(WEIGHTS.values()), 2)
final_score = round(weighted_avg * context_multiplier, 2)
bucket = _bucket_for_score(final_score)

with calc_col2:
    st.metric("Weighted Avg", weighted_avg)
    st.metric("Final Score", final_score)
    st.metric("Bucket", bucket)

st.markdown(
    f"""
`weighted_sum = A*{WEIGHTS["A"]} + B*{WEIGHTS["B"]} + C*{WEIGHTS["C"]} = {round(weighted_sum, 2)}`
    """
)

st.json(
    {
        "weights": WEIGHTS,
        "contribution_breakdown": {
            "A_weighted_contribution": round(a_score * WEIGHTS["A"], 2),
            "B_weighted_contribution": round(b_score * WEIGHTS["B"], 2),
            "C_weighted_contribution": round(c_score * WEIGHTS["C"], 2),
        },
        "weighted_average_0_10": weighted_avg,
        "context_multiplier": context_multiplier,
        "final_score": final_score,
        "bucket": bucket,
    }
)
