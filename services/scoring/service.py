from __future__ import annotations

import asyncio
import re
from dataclasses import asdict, dataclass
from typing import Any


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _contains_any(text: str, terms: list[str]) -> int:
    return sum(1 for term in terms if term in text)


@dataclass
class FeatureSet:
    transcript_available: bool
    transcript_source: str
    mastery_mentions: int
    autonomy_mentions: int
    mission_signal_count: int
    q5_leadership_level: str
    question_coverage_ratio: float
    form_text: str
    activities_text: str
    honors_text: str
    essay_failure_text: str
    essay_beta_text: str

    @staticmethod
    def from_candidate_data(candidate_data: dict[str, Any]) -> FeatureSet:
        parser_context = candidate_data.get("parser_context", {})
        results = parser_context.get("results", {}) if isinstance(parser_context, dict) else {}
        video_task = results.get("video_task", {}) if isinstance(results, dict) else {}

        transcript_available = False
        transcript_source = "none"
        mastery_mentions = 0
        autonomy_mentions = 0
        mission_signal_count = 0
        q5_leadership_level = "none"
        question_coverage_ratio = 0.0

        if isinstance(video_task, dict) and str(video_task.get("status", "")).upper() == "SUCCESS":
            video_result = video_task.get("result", {})
            transcript = video_result.get("transcript", {}) if isinstance(video_result, dict) else {}
            analysis = video_result.get("analysis", {}) if isinstance(video_result, dict) else {}
            signals = analysis.get("signals", {}) if isinstance(analysis, dict) else {}
            intrinsic = signals.get("intrinsic", {}) if isinstance(signals, dict) else {}
            mission = signals.get("mission_alignment", {}) if isinstance(signals, dict) else {}

            intrinsic_signals = intrinsic.get("signals", {}) if isinstance(intrinsic, dict) else {}
            mastery_mentions = len(intrinsic_signals.get("mastery_mentions", [])) if isinstance(intrinsic_signals, dict) else 0
            autonomy_mentions = len(intrinsic_signals.get("autonomy_mentions", [])) if isinstance(intrinsic_signals, dict) else 0
            mission_signal_count = int(mission.get("signal_count", 0)) if isinstance(mission, dict) else 0

            coverage = analysis.get("question_coverage", []) if isinstance(analysis, dict) else []
            if isinstance(coverage, list):
                q5 = next((item for item in coverage if item.get("question_id") == "q5_leadership"), None)
                if isinstance(q5, dict):
                    q5_leadership_level = str(q5.get("coverage_level", "none")).lower()

            try:
                question_coverage_ratio = float(analysis.get("question_coverage_ratio", 0.0)) if isinstance(analysis, dict) else 0.0
            except (TypeError, ValueError):
                question_coverage_ratio = 0.0

            transcript_available = bool(transcript.get("available", False)) if isinstance(transcript, dict) else False
            transcript_source = str(transcript.get("source", "none")) if isinstance(transcript, dict) else "none"

        form_data = candidate_data.get("form_data", {})
        form_data = form_data if isinstance(form_data, dict) else {}

        values_text = [_normalize_text(v) for v in form_data.values()]
        form_text = "\n".join([txt for txt in values_text if txt])

        activities_chunks: list[str] = []
        honors_chunks: list[str] = []
        for key, value in form_data.items():
            key_l = _normalize_text(key)
            val_l = _normalize_text(value)
            if not val_l:
                continue
            if "activity" in key_l or "leadership description" in key_l or "organization name" in key_l:
                activities_chunks.append(val_l)
            if "honor" in key_l or "recognition" in key_l or "award" in key_l:
                honors_chunks.append(val_l)

        essay_failure_text = _normalize_text(
            form_data.get(
                "Reflect on a situation where your efforts or plan significantly failed. How exactly did you analyze what happened, and what new strategy did you choose to move forward? (Max characters: 100)",
                "",
            )
            or candidate_data.get("essay_failure", "")
        )
        essay_beta_text = _normalize_text(
            form_data.get(
                'The concept of "perpetual beta" means a constant readiness to update your knowledge and admit mistakes. Describe a skill, idea, or project of yours that is currently in "perpetual beta." How exactly are you challenging yourself to improve it? (Max characters: 100)',
                "",
            )
            or candidate_data.get("essay_beta", "")
            or candidate_data.get("essay", "")
        )

        return FeatureSet(
            transcript_available=transcript_available,
            transcript_source=transcript_source,
            mastery_mentions=max(0, mastery_mentions),
            autonomy_mentions=max(0, autonomy_mentions),
            mission_signal_count=max(0, mission_signal_count),
            q5_leadership_level=q5_leadership_level,
            question_coverage_ratio=max(0.0, min(1.0, question_coverage_ratio)),
            form_text=form_text,
            activities_text="\n".join(activities_chunks),
            honors_text="\n".join(honors_chunks),
            essay_failure_text=essay_failure_text,
            essay_beta_text=essay_beta_text,
        )


@dataclass
class BlockAResult:
    duration_commitment_0_4: float
    vertical_progress_0_3: float
    achievements_0_3: float
    total_0_10: float


@dataclass
class BlockBResult:
    reaction_to_failure_0_5: float
    challenge_orientation_0_5: float
    total_0_10: float


@dataclass
class BlockCResult:
    intrinsic_type_i_0_4: float
    mission_alignment_0_6: float
    total_0_10: float
    weighted_0_15: float
    source: str


@dataclass
class AggregationResult:
    weights: dict[str, float]
    weighted_sum: float
    weighted_average_0_10: float
    context_multiplier: float
    final_score: float


@dataclass
class ExplainabilityResult:
    summary: str
    block_explanations: dict[str, str]
    contribution_breakdown: dict[str, float]
    confidence: str
    recommendation: str


BUCKET_THRESHOLDS = {
    "A": (8.5, 15.0),
    "B": (5.0, 8.49),
    "C": (0.0, 4.99),
}


def score_block_a(features: FeatureSet) -> BlockAResult:
    text = f"{features.activities_text}\n{features.honors_text}\n{features.form_text}"

    # 2 points per long-term activity (>2 years), up to 4.
    long_term_matches = re.findall(r"\b([2-9]|[1-9]\d)\+?\s*(years|yrs|year)\b", text)
    duration_commitment = float(min(4, len(long_term_matches) * 2))

    vertical_progress_terms = [
        "captain",
        "president",
        "leader",
        "led",
        "head",
        "coordinator",
        "coordinated",
        "mentor",
        "promoted",
        "elected",
    ]
    vertical_progress = 3.0 if _contains_any(text, vertical_progress_terms) > 0 else 0.0

    achievement_terms = [
        "award",
        "winner",
        "won",
        "medal",
        "prize",
        "published",
        "certificate",
        "rank",
        "top",
        "completed project",
        "launched",
    ]
    achievements = 3.0 if _contains_any(text, achievement_terms) > 0 else 0.0

    total = min(10.0, duration_commitment + vertical_progress + achievements)
    return BlockAResult(
        duration_commitment_0_4=duration_commitment,
        vertical_progress_0_3=vertical_progress,
        achievements_0_3=achievements,
        total_0_10=total,
    )


def score_block_b(features: FeatureSet) -> BlockBResult:
    failure_text = features.essay_failure_text
    beta_text = features.essay_beta_text

    analysis_terms = ["analyze", "analysis", "reflect", "root cause", "mistake", "lesson learned", "learned"]
    strategy_terms = ["strategy", "changed", "improved", "next time", "plan", "adapt", "iterate"]
    blame_terms = ["not my fault", "blame", "unfair", "gave up", "quit", "i can't"]

    analysis_hits = _contains_any(failure_text, analysis_terms)
    strategy_hits = _contains_any(failure_text, strategy_terms)
    blame_hits = _contains_any(failure_text, blame_terms)

    reaction_to_failure = 1.0 + min(2.0, float(analysis_hits)) + min(2.0, float(strategy_hits))
    if failure_text == "":
        reaction_to_failure = 0.0
    reaction_to_failure = max(0.0, min(5.0, reaction_to_failure - min(2.0, float(blame_hits))))

    challenge_terms = ["challenge", "difficult", "hard", "stretch", "comfort zone", "risk"]
    growth_terms = ["learn", "improve", "beta", "iterate", "feedback", "experiment", "practice", "update"]
    avoidance_terms = ["easy tasks", "avoid challenge", "simple tasks only", "don't like challenge"]

    challenge_hits = _contains_any(beta_text, challenge_terms)
    growth_hits = _contains_any(beta_text, growth_terms)
    avoidance_hits = _contains_any(beta_text, avoidance_terms)

    challenge_orientation = 1.0 + min(2.0, float(challenge_hits)) + min(2.0, float(growth_hits))
    if beta_text == "":
        challenge_orientation = 0.0
    challenge_orientation = max(0.0, min(5.0, challenge_orientation - min(2.0, float(avoidance_hits))))

    total = min(10.0, reaction_to_failure + challenge_orientation)
    return BlockBResult(
        reaction_to_failure_0_5=reaction_to_failure,
        challenge_orientation_0_5=challenge_orientation,
        total_0_10=total,
    )


def score_block_c(features: FeatureSet) -> BlockCResult:
    intrinsic_score = float(min(4, min(2, features.mastery_mentions) + min(2, features.autonomy_mentions)))
    mission_score = float(min(6, features.mission_signal_count))
    raw_score = float(min(10, intrinsic_score + mission_score))
    weighted_score = round(raw_score * 1.5, 2)
    source = "parser_signals" if features.transcript_available else "fallback_no_video"
    return BlockCResult(
        intrinsic_type_i_0_4=intrinsic_score,
        mission_alignment_0_6=mission_score,
        total_0_10=raw_score,
        weighted_0_15=weighted_score,
        source=source,
    )


def aggregate_scores(
    block_a: BlockAResult,
    block_b: BlockBResult,
    block_c: BlockCResult,
    context_multiplier: float = 1.0,
) -> AggregationResult:
    weights = {"A": 2.0, "B": 3.0, "C": 1.5}
    weighted_sum = (
        block_a.total_0_10 * weights["A"]
        + block_b.total_0_10 * weights["B"]
        + block_c.total_0_10 * weights["C"]
    )
    weighted_average_0_10 = round(weighted_sum / sum(weights.values()), 2)
    final_score = round(weighted_average_0_10 * context_multiplier, 2)
    return AggregationResult(
        weights=weights,
        weighted_sum=round(weighted_sum, 2),
        weighted_average_0_10=weighted_average_0_10,
        context_multiplier=context_multiplier,
        final_score=final_score,
    )


def assign_bucket(final_score: float, thresholds: dict[str, tuple[float, float]] = BUCKET_THRESHOLDS) -> str:
    for bucket, (lower, upper) in thresholds.items():
        if lower <= final_score <= upper:
            return bucket
    return "C"


def build_explainability(
    features: FeatureSet,
    block_a: BlockAResult,
    block_b: BlockBResult,
    block_c: BlockCResult,
    aggregation: AggregationResult,
    bucket: str,
) -> ExplainabilityResult:
    contribution_breakdown = {
        "A_weighted_contribution": round(block_a.total_0_10 * aggregation.weights["A"], 2),
        "B_weighted_contribution": round(block_b.total_0_10 * aggregation.weights["B"], 2),
        "C_weighted_contribution": round(block_c.total_0_10 * aggregation.weights["C"], 2),
    }

    block_explanations = {
        "A": (
            f"A={block_a.total_0_10}/10: duration_commitment={block_a.duration_commitment_0_4}/4, "
            f"vertical_progress={block_a.vertical_progress_0_3}/3, achievements={block_a.achievements_0_3}/3."
        ),
        "B": (
            f"B={block_b.total_0_10}/10: reaction_to_failure={block_b.reaction_to_failure_0_5}/5, "
            f"challenge_orientation={block_b.challenge_orientation_0_5}/5."
        ),
        "C": (
            f"C={block_c.total_0_10}/10 from video signals: intrinsic={block_c.intrinsic_type_i_0_4}/4, "
            f"mission_alignment={block_c.mission_alignment_0_6}/6, source={block_c.source}."
        ),
    }

    if not features.transcript_available:
        confidence = "low"
    elif features.question_coverage_ratio >= 0.6:
        confidence = "high"
    else:
        confidence = "medium"

    recommendation = {
        "A": "Recommended for strong consideration/admission review.",
        "B": "Requires committee interview and targeted validation.",
        "C": "High risk fit; requires careful manual review.",
    }.get(bucket, "Requires manual review.")

    summary = (
        f"Final score {aggregation.final_score} (bucket {bucket}) from weighted blocks: "
        f"A={block_a.total_0_10}, B={block_b.total_0_10}, C={block_c.total_0_10}. "
        f"Confidence={confidence}."
    )

    return ExplainabilityResult(
        summary=summary,
        block_explanations=block_explanations,
        contribution_breakdown=contribution_breakdown,
        confidence=confidence,
        recommendation=recommendation,
    )


class ScoringService:
    async def evaluate_candidate(self, candidate_data: dict) -> dict:
        await asyncio.sleep(0.2)

        features = FeatureSet.from_candidate_data(candidate_data)
        block_a = score_block_a(features)
        block_b = score_block_b(features)
        block_c = score_block_c(features)
        aggregation = aggregate_scores(block_a, block_b, block_c, context_multiplier=1.0)
        final_score = aggregation.final_score
        bucket = assign_bucket(final_score)
        explainability = build_explainability(features, block_a, block_b, block_c, aggregation, bucket)

        leadership_score = 8.0 if features.q5_leadership_level == "full" else (6.0 if features.q5_leadership_level == "partial" else 5.0)
        experience_score = block_a.total_0_10
        motivation_score = block_c.total_0_10
        growth_score = block_b.total_0_10
        authenticity_score = 8.0 if features.transcript_available else 5.0

        red_flags: list[str] = []
        if block_c.total_0_10 == 0:
            red_flags.append("No strong motivation evidence in video signals")
        if block_b.total_0_10 <= 2:
            red_flags.append("Weak growth-mindset evidence in essays")

        green_flags: list[str] = []
        if block_a.total_0_10 >= 7:
            green_flags.append("Strong grit profile from sustained activities and achievements")
        if block_b.total_0_10 >= 7:
            green_flags.append("Strong reflective learning and challenge orientation")
        if block_c.total_0_10 >= 7:
            green_flags.append("Strong intrinsic motivation and mission alignment")

        return {
            "scores": {
                "leadership": leadership_score,
                "experience": experience_score,
                "motivation": motivation_score,
                "growth": growth_score,
                "authenticity": authenticity_score,
            },
            "overall_score": final_score,
            "final_score": final_score,
            "bucket": bucket,
            "weights": aggregation.weights,
            "context_multiplier": aggregation.context_multiplier,
            "aggregation": asdict(aggregation),
            "block_breakdown": {
                "A": asdict(block_a),
                "B": asdict(block_b),
                "C": asdict(block_c),
            },
            "explainability_summary": explainability.summary,
            "explainability": asdict(explainability),
            "red_flags": red_flags,
            "green_flags": green_flags,
            "features": asdict(features),
        }
