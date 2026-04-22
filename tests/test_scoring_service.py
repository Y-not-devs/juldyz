from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
project_root_str = str(PROJECT_ROOT)
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from services.scoring.service import ScoringService


class ScoringServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_scoring_uses_multimodal_profile(self) -> None:
        payload = {
            "candidate_profile": {
                "form": {
                    "raw": {
                        "Name": "Test",
                        "Surname": "User",
                        "Reflect on a situation where your efforts or plan significantly failed. How exactly did you analyze what happened, and what new strategy did you choose to move forward? (Max characters: 120)": "I reflected, changed strategy, and improved.",
                        'The concept of "Jas Ulan" here means consistent readiness to update your knowledge and skills. Describe a skill, experience or issue in your life that currently is "outdated" for you. How exactly are you challenging yourself to improve it? (Max characters: 120)': "I keep improving my engineering skills through hard projects.",
                    }
                },
                "essay": {
                    "llm_parsed_ok": True,
                    "analysis": {
                        "scores": {
                            "growth_mindset": 8,
                            "resilience": 9,
                            "motivation_clarity": 8,
                            "mission_alignment": 7,
                            "authenticity_confidence": 8,
                        }
                    },
                },
                "video": {
                    "task_status": "SUCCESS",
                    "data": {
                        "transcript": {"available": True, "source": "youtube_captions"},
                        "analysis": {
                            "signals": {
                                "intrinsic": {
                                    "signals": {
                                        "mastery_mentions": ["learn"],
                                        "autonomy_mentions": ["self-driven"],
                                    }
                                },
                                "mission_alignment": {"signal_count": 4},
                            },
                            "question_coverage": [
                                {"question_id": "q5_leadership", "coverage_level": "partial"}
                            ],
                            "question_coverage_ratio": 0.8,
                        },
                    },
                },
                "pdf": {
                    "task_status": "SUCCESS",
                    "data": {
                        "pdf_summary": {"page_count": 2},
                        "extracted_profile": {
                            "skills": ["python", "sql"],
                            "emails": ["a@b.com"],
                            "phones": ["123"],
                        },
                    },
                },
                "github": {
                    "task_status": "SUCCESS",
                    "data": {
                        "profile_summary": {
                            "public_repos": 5,
                            "followers": 2,
                            "has_bio": True,
                            "has_blog": False,
                            "has_company": True,
                        }
                    },
                },
            }
        }

        result = await ScoringService().evaluate_candidate(payload)

        self.assertEqual(result["max_score"], 10.0)
        self.assertTrue(result["block_breakdown"]["B"]["llm_support_used"])
        self.assertEqual(result["block_breakdown"]["C"]["source"], "video_plus_essay_llm")
        self.assertIn("PDF evidence parsed successfully", result["green_flags"])
        self.assertIn("GitHub evidence parsed successfully", result["green_flags"])
        self.assertNotIn("essay_llm_unavailable", result["degradation_notes"])
        self.assertNotIn("pdf_not_available", result["degradation_notes"])
        self.assertFalse(result["persistence"]["saved"])


if __name__ == "__main__":
    unittest.main()
