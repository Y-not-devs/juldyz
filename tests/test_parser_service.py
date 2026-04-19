from __future__ import annotations

import unittest
from unittest.mock import patch

from services.parser.service import ParserService


class ParserServiceTests(unittest.TestCase):
    def test_queue_tasks_marks_file_task_failure_without_crashing_parse(self) -> None:
        with patch.object(
            ParserService,
            "_prepare_pdf_file",
            side_effect=ValueError("file_url did not return a PDF document"),
        ), patch(
            "services.parser.service.parse_essay_task",
            return_value={"analysis": {"scores": {}}, "llm_parsed_ok": False},
        ):
            result = ParserService.queue_tasks(
                user_id="1",
                file_url="https://example.com/not-a-pdf",
                essay_text="I learned from failure.",
            )

        self.assertEqual(result["status"], "completed_with_errors")
        self.assertEqual(result["results"]["file_task"]["status"], "FAILURE")
        self.assertEqual(
            result["results"]["file_task"]["error"],
            "file_url did not return a PDF document",
        )
        self.assertEqual(result["results"]["essay_task"]["status"], "SUCCESS")
        self.assertEqual(result["summary"]["success_count"], 1)
        self.assertEqual(result["summary"]["failure_count"], 1)

    def test_queue_tasks_returns_completed_with_errors_when_only_file_fails(self) -> None:
        with patch.object(
            ParserService,
            "_prepare_pdf_file",
            side_effect=ValueError("file_url did not return a PDF document"),
        ):
            result = ParserService.queue_tasks(
                user_id="1",
                file_url="https://example.com/not-a-pdf",
            )

        self.assertEqual(result["status"], "completed_with_errors")
        self.assertEqual(result["results"]["file_task"]["status"], "FAILURE")
        self.assertEqual(result["summary"]["requested_tasks"], 1)
        self.assertEqual(result["summary"]["success_count"], 0)
        self.assertEqual(result["summary"]["failure_count"], 1)

    def test_queue_tasks_reuses_cached_video_and_essay_results(self) -> None:
        cached_video = {
            "status": "success",
            "user_id": "1",
            "video_id": "eBz7iUJu9UM",
            "analysis": {"question_coverage": []},
            "transcript": {"available": True, "source": "cache"},
        }
        cached_essay = {
            "status": "success",
            "user_id": "1",
            "essay_char_count": 5,
            "llm_parsed_ok": False,
            "analysis": None,
        }

        with patch.object(ParserService, "_load_cached_video_task", return_value=cached_video), patch.object(
            ParserService,
            "_load_cached_essay_task",
            return_value=cached_essay,
        ), patch(
            "services.parser.service.parse_video_task",
            side_effect=AssertionError("video parser should not run when cache exists"),
        ), patch(
            "services.parser.service.parse_essay_task",
            side_effect=AssertionError("essay parser should not run when cache exists"),
        ):
            result = ParserService.queue_tasks(
                user_id="1",
                youtube_url="https://youtu.be/eBz7iUJu9UM",
                essay_text="hello",
            )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["results"]["video_task"]["status"], "SUCCESS")
        self.assertEqual(result["results"]["video_task"]["result"]["transcript"]["source"], "cache")
        self.assertEqual(result["results"]["essay_task"]["status"], "SUCCESS")
        self.assertFalse(result["results"]["essay_task"]["result"]["llm_parsed_ok"])


if __name__ == "__main__":
    unittest.main()
