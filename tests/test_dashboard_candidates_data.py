from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
project_root_str = str(PROJECT_ROOT)
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from services.dashboard.candidates_data import (
    build_table_rows,
    candidate_display_name,
    fetch_candidates,
    row_matches,
)
from tests.test_support import temp_database


class DashboardCandidatesDataTests(unittest.TestCase):
    def test_fetch_candidates_and_build_table_rows(self) -> None:
        with temp_database() as temp_db:
            user_id = temp_db.upsert_user("tg_dashboard")
            temp_db.upsert_telegram_user(
                telegram_id="tg_dashboard",
                username="dash_user",
                first_name="Telegram",
                last_name="User",
            )
            response_id = temp_db.save_candidate_response(
                user_id,
                {
                    "Name": "Aruzhan",
                    "Surname": "Sapar",
                    "Email Address": "aruzhan@example.com",
                    "Which program are you applying for?": "Undergraduate",
                    "Please specify your intended major": "Computer Science",
                },
            )
            temp_db.update_candidate_response_processing(response_id, "done")
            temp_db.update_candidate_response_stage(response_id, "parser", "done")
            temp_db.update_candidate_response_stage(response_id, "scoring", "done")
            temp_db.save_score(
                user_id,
                scores={
                    "motivation": 8.0,
                    "experience": 7.0,
                    "leadership": 6.0,
                    "growth": 9.0,
                    "total": 7.8,
                },
                explanation={"summary": "ok"},
                ai_suspicion="low",
            )

            rows = fetch_candidates(limit=10, database=temp_db)
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(candidate_display_name(row), "Aruzhan Sapar")
            self.assertTrue(row_matches(row, search_text="aruzhan"))
            self.assertFalse(row_matches(row, only_scored=True, min_score=8.0))

            table_rows = build_table_rows(rows)
            self.assertEqual(table_rows[0]["score_out_of"], "7.80 / 10")
            self.assertEqual(table_rows[0]["parser"], "done")
            self.assertEqual(table_rows[0]["scoring"], "done")


if __name__ == "__main__":
    unittest.main()
