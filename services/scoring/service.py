import asyncio
from typing import Any


class ScoringService:
    def __init__(self):
        pass

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _extract_video_result(candidate_data: dict[str, Any]) -> dict[str, Any] | None:
        parser_context = candidate_data.get("parser_context", {})
        if not isinstance(parser_context, dict):
            return None

        results = parser_context.get("results", {})
        if not isinstance(results, dict):
            return None

        video_task = results.get("video_task", {})
        if not isinstance(video_task, dict):
            return None

        if str(video_task.get("status", "")).upper() != "SUCCESS":
            return None

        video_result = video_task.get("result", {})
        if isinstance(video_result, dict):
            return video_result
        return None

    @staticmethod
    def _compute_block_c_from_parser(video_result: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(video_result, dict):
            return {
                "intrinsic_type_i_0_4": 0.0,
                "mission_alignment_0_6": 0.0,
                "raw_0_10": 0.0,
                "weighted_0_15": 0.0,
                "source": "fallback_no_video",
            }

        analysis = video_result.get("analysis", {})
        if not isinstance(analysis, dict):
            return {
                "intrinsic_type_i_0_4": 0.0,
                "mission_alignment_0_6": 0.0,
                "raw_0_10": 0.0,
                "weighted_0_15": 0.0,
                "source": "fallback_no_analysis",
            }

        signals = analysis.get("signals", {})
        if not isinstance(signals, dict):
            return {
                "intrinsic_type_i_0_4": 0.0,
                "mission_alignment_0_6": 0.0,
                "raw_0_10": 0.0,
                "weighted_0_15": 0.0,
                "source": "fallback_no_signals",
            }

        intrinsic = signals.get("intrinsic", {})
        mission = signals.get("mission_alignment", {})

        mastery_mentions = len(intrinsic.get("signals", {}).get("mastery_mentions", [])) if isinstance(intrinsic, dict) else 0
        autonomy_mentions = len(intrinsic.get("signals", {}).get("autonomy_mentions", [])) if isinstance(intrinsic, dict) else 0
        mission_mentions = mission.get("signal_count", 0) if isinstance(mission, dict) else 0

        intrinsic_score = min(4.0, float(min(2, mastery_mentions) + min(2, autonomy_mentions)))
        mission_score = min(6.0, float(max(0, int(mission_mentions))))
        raw_score = min(10.0, intrinsic_score + mission_score)
        weighted_score = round(raw_score * 1.5, 2)

        return {
            "intrinsic_type_i_0_4": intrinsic_score,
            "mission_alignment_0_6": mission_score,
            "raw_0_10": raw_score,
            "weighted_0_15": weighted_score,
            "source": "parser_signals",
        }

    @staticmethod
    def _compute_leadership_from_coverage(video_result: dict[str, Any] | None) -> float:
        if not isinstance(video_result, dict):
            return 5.0

        coverage = video_result.get("analysis", {}).get("question_coverage", [])
        if not isinstance(coverage, list):
            return 5.0

        q5 = next((item for item in coverage if item.get("question_id") == "q5_leadership"), None)
        if not isinstance(q5, dict):
            return 5.0

        level = str(q5.get("coverage_level", "none")).lower()
        if level == "full":
            return 8.0
        if level == "partial":
            return 6.0
        return 5.0

    async def evaluate_candidate(self, candidate_data: dict) -> dict:
        await asyncio.sleep(0.2)

        github_stats = candidate_data.get("github_stats", {})
        commits = github_stats.get("total_commits", 0) if isinstance(github_stats, dict) else 0
        experience_score = min(10.0, float((commits // 50) + 4)) if commits > 0 else 5.0

        video_result = self._extract_video_result(candidate_data)
        block_c = self._compute_block_c_from_parser(video_result)
        motivation_score = round(min(10.0, max(0.0, (block_c["weighted_0_15"] / 15.0) * 10.0)), 1)

        leadership_score = self._compute_leadership_from_coverage(video_result)
        authenticity_score = 8.0 if video_result else 5.0

        overall = round((leadership_score + experience_score + motivation_score + authenticity_score) / 4, 1)

        red_flags = []
        if commits < 10:
            red_flags.append("Low profile activity")
        if block_c["weighted_0_15"] == 0:
            red_flags.append("No strong motivation evidence in video signals")

        return {
            "scores": {
                "leadership": leadership_score,
                "experience": experience_score,
                "motivation": motivation_score,
                "authenticity": authenticity_score,
            },
            "overall_score": overall,
            "explanation": "Scored from parser extraction signals. Block C is computed in scoring-service.",
            "red_flags": red_flags,
            "green_flags": ["Initiative", "Has practical examples"],
            "block_c_breakdown": block_c,
        }
