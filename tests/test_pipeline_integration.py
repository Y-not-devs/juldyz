from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
project_root_str = str(PROJECT_ROOT)
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from fastapi.testclient import TestClient

from core.orchestrator import CandidateWorkflow
from services.form import main as form_main
from services.form.schemas.payload import FormSubmitRequest
from services.parser import main as parser_main
from services.scoring import main as scoring_main
from tests.test_support import patch_module_dbs, temp_database


class FormPipelineIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_form_submit_persists_normalized_response_and_enqueues_job(self) -> None:
        with temp_database() as temp_db, patch_module_dbs(temp_db, "services.form.service"):
            user_id = temp_db.upsert_user("tg_form_submit")

            response = await form_main.form_submit(
                FormSubmitRequest(
                    tg_id="tg_form_submit",
                    data={
                        "Name": "Aruzhan",
                        "Surname": "Sapar",
                        "Which program are you applying for?": "Undergraduate",
                        "Please specify your intended major": "Computer Science",
                    },
                )
            )

            self.assertEqual(response["status"], "accepted")
            self.assertEqual(response["candidate_id"], str(user_id))

            saved_response = temp_db.get_candidate_response_by_id(response["response_id"])
            self.assertIsNotNone(saved_response)
            self.assertEqual(saved_response["first_name"], "Aruzhan")
            self.assertEqual(saved_response["last_name"], "Sapar")
            self.assertEqual(saved_response["program_applied"], "Undergraduate")
            self.assertEqual(saved_response["major"], "Computer Science")
            self.assertEqual(saved_response["processing_status"], "pending")

            with temp_db._connect() as conn:
                job_row = conn.execute(
                    "SELECT * FROM workflow_jobs WHERE response_id=?",
                    (int(response["response_id"]),),
                ).fetchone()

            self.assertIsNotNone(job_row)
            job_payload = json.loads(job_row["payload_json"])
            self.assertEqual(job_payload["Name"], "Aruzhan")
            self.assertNotIn("data", job_payload)

    async def test_process_workflow_job_marks_successful_stage_statuses(self) -> None:
        with temp_database() as temp_db, patch_module_dbs(temp_db, "services.form.service"):
            user_id = temp_db.upsert_user("tg_workflow_ok")
            response_id = temp_db.save_candidate_response(
                user_id,
                {"Name": "Dana", "Surname": "Sarsen", "tg_id": "tg_workflow_ok"},
            )
            job_id = temp_db.enqueue_workflow_job(
                response_id,
                user_id,
                {"Name": "Dana", "Surname": "Sarsen", "tg_id": "tg_workflow_ok", "candidate_id": str(user_id)},
                max_attempts=3,
            )
            job = temp_db.claim_next_workflow_job()
            self.assertEqual(job["id"], job_id)

            class FakeOrchestrator:
                async def handle_form_submission(self, raw_payload: dict, stage_callback=None):
                    self.raw_payload = raw_payload
                    if stage_callback:
                        stage_callback("parser", "processing", None)
                        stage_callback("parser", "done", None)
                        stage_callback("scoring", "processing", None)
                        stage_callback("scoring", "done", None)
                        stage_callback("notification", "skipped", None)
                    return {"status": "ok"}

            fake_orchestrator = FakeOrchestrator()
            with patch.object(form_main, "orchestrator", fake_orchestrator):
                await form_main._process_workflow_job(job)

            saved_response = temp_db.get_candidate_response_by_id(response_id)
            self.assertEqual(saved_response["processing_status"], "done")
            self.assertEqual(saved_response["parser_status"], "done")
            self.assertEqual(saved_response["scoring_status"], "done")
            self.assertEqual(saved_response["notification_status"], "skipped")
            self.assertEqual(fake_orchestrator.raw_payload["candidate_id"], str(user_id))

            with temp_db._connect() as conn:
                saved_job = conn.execute("SELECT * FROM workflow_jobs WHERE id=?", (job_id,)).fetchone()
            self.assertEqual(saved_job["status"], "completed")
            self.assertEqual(saved_job["current_stage"], "completed")

    async def test_process_workflow_job_marks_dead_letter_on_final_failure(self) -> None:
        with temp_database() as temp_db, patch_module_dbs(temp_db, "services.form.service"):
            user_id = temp_db.upsert_user("tg_workflow_fail")
            response_id = temp_db.save_candidate_response(
                user_id,
                {"Name": "Fail", "Surname": "Case", "tg_id": "tg_workflow_fail"},
            )
            job_id = temp_db.enqueue_workflow_job(
                response_id,
                user_id,
                {"Name": "Fail", "Surname": "Case", "tg_id": "tg_workflow_fail", "candidate_id": str(user_id)},
                max_attempts=1,
            )
            job = temp_db.claim_next_workflow_job()

            class FakeOrchestrator:
                async def handle_form_submission(self, raw_payload: dict, stage_callback=None):
                    raise RuntimeError("simulated pipeline crash")

            with patch.object(form_main, "orchestrator", FakeOrchestrator()):
                await form_main._process_workflow_job(job)

            saved_response = temp_db.get_candidate_response_by_id(response_id)
            self.assertEqual(saved_response["processing_status"], "failed")
            self.assertIn("simulated pipeline crash", saved_response["processing_error"])

            with temp_db._connect() as conn:
                saved_job = conn.execute("SELECT * FROM workflow_jobs WHERE id=?", (job_id,)).fetchone()
            self.assertEqual(saved_job["status"], "dead_letter")
            self.assertEqual(saved_job["current_stage"], "dead_letter")

    async def test_process_workflow_job_marks_current_stage_failed_before_retry(self) -> None:
        with temp_database() as temp_db, patch_module_dbs(temp_db, "services.form.service"):
            user_id = temp_db.upsert_user("tg_workflow_retry")
            response_id = temp_db.save_candidate_response(
                user_id,
                {"Name": "Retry", "Surname": "Case", "tg_id": "tg_workflow_retry"},
            )
            job_id = temp_db.enqueue_workflow_job(
                response_id,
                user_id,
                {"Name": "Retry", "Surname": "Case", "tg_id": "tg_workflow_retry", "candidate_id": str(user_id)},
                max_attempts=3,
            )
            job = temp_db.claim_next_workflow_job()

            class FakeOrchestrator:
                async def handle_form_submission(self, raw_payload: dict, stage_callback=None):
                    if stage_callback:
                        stage_callback("parser", "processing", None)
                    raise RuntimeError("parser upstream timeout")

            with patch.object(form_main, "orchestrator", FakeOrchestrator()):
                await form_main._process_workflow_job(job)

            saved_response = temp_db.get_candidate_response_by_id(response_id)
            self.assertEqual(saved_response["processing_status"], "pending")
            self.assertEqual(saved_response["parser_status"], "failed")
            self.assertIn("parser upstream timeout", saved_response["parser_error"])

            with temp_db._connect() as conn:
                saved_job = conn.execute("SELECT * FROM workflow_jobs WHERE id=?", (job_id,)).fetchone()
            self.assertEqual(saved_job["status"], "retry")
            self.assertEqual(saved_job["current_stage"], "queued")


class OrchestratorContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_workflow_builds_multimodal_scoring_payload(self) -> None:
        workflow = CandidateWorkflow(
            {
                "bot": "http://bot",
                "scoring": "http://scoring",
                "parser": "http://parser",
            }
        )

        recorded_calls: list[tuple[str, dict]] = []

        async def fake_parser_request(endpoint: str, payload: dict):
            recorded_calls.append((f"parser:{endpoint}", payload))
            return {
                "status": "completed",
                "results": {
                    "essay_task": {
                        "status": "SUCCESS",
                        "result": {
                            "analysis": {
                                "scores": {
                                    "growth_mindset": 8,
                                    "resilience": 9,
                                    "motivation_clarity": 7,
                                    "mission_alignment": 8,
                                    "authenticity_confidence": 8,
                                }
                            },
                            "llm_parsed_ok": True,
                        },
                    },
                    "video_task": {
                        "status": "SUCCESS",
                        "result": {
                            "transcript": {"available": True, "source": "youtube_captions"},
                            "analysis": {
                                "signals": {
                                    "intrinsic": {
                                        "signals": {
                                            "mastery_mentions": ["learn"],
                                            "autonomy_mentions": ["build"],
                                        }
                                    },
                                    "mission_alignment": {"signal_count": 3},
                                },
                                "question_coverage": [
                                    {"question_id": "q5_leadership", "coverage_level": "full"}
                                ],
                                "question_coverage_ratio": 0.8,
                            },
                        },
                    },
                    "file_task": {
                        "status": "SUCCESS",
                        "result": {
                            "pdf_summary": {"page_count": 2},
                            "extracted_profile": {
                                "skills": ["python"],
                                "emails": ["a@b.com"],
                                "phones": [],
                            },
                        },
                    },
                    "github_task": {
                        "status": "SUCCESS",
                        "result": {
                            "profile_summary": {
                                "public_repos": 4,
                                "followers": 2,
                                "has_bio": True,
                                "has_blog": False,
                                "has_company": True,
                            }
                        },
                    },
                },
            }

        async def fake_scoring_request(endpoint: str, payload: dict):
            recorded_calls.append((f"scoring:{endpoint}", payload))
            return {"status": "success", "data": {"persistence": {"saved": True}}}

        async def fake_bot_request(endpoint: str, payload: dict):
            recorded_calls.append((f"bot:{endpoint}", payload))
            return {"status": "ok"}

        workflow.parser_pipeline.send_request = fake_parser_request
        workflow.scoring_pipeline.send_request = fake_scoring_request
        workflow.bot_pipeline.send_request = fake_bot_request

        stages: list[tuple[str, str]] = []
        result = await workflow.process_form_submission(
            {
                "tg_id": "12345",
                "candidate_id": "7",
                "Name": "Aruzhan",
                "Surname": "Sapar",
                "Personal Presentation (Undergraduate)": "https://youtu.be/example123",
                "Additional documents": "https://drive.google.com/file/d/test-pdf/view",
                "GitHub URL": "https://github.com/example-user",
                "Reflect on a situation where your efforts or plan significantly failed. How exactly did you analyze what happened, and what new strategy did you choose to move forward? (Max characters: 100)": "I reflected and improved.",
                'The concept of "Jas Ulan" here means consistent readiness to update your knowledge and skills. Describe a skill, experience or issue in your life that currently is "outdated" for you. How exactly are you challenging yourself to improve it? (Max characters: 120)': "I keep improving with real projects.",
            },
            stage_callback=lambda stage, status, detail=None: stages.append((stage, status)),
        )

        parser_call = next(payload for name, payload in recorded_calls if name == "parser:parse")
        scoring_call = next(payload for name, payload in recorded_calls if name == "scoring:evaluate")
        bot_call = next(payload for name, payload in recorded_calls if name == "bot:notify")

        self.assertEqual(parser_call["user_id"], "7")
        self.assertEqual(parser_call["github_url"], "https://github.com/example-user")
        self.assertEqual(parser_call["file_url"], "https://drive.google.com/file/d/test-pdf/view")
        self.assertEqual(parser_call["youtube_url"], "https://youtu.be/example123")
        self.assertTrue(parser_call["essay_text"])

        profile = scoring_call["candidate_profile"]
        self.assertEqual(profile["form"]["first_name"], "Aruzhan")
        self.assertTrue(profile["essay"]["llm_parsed_ok"])
        self.assertEqual(profile["video"]["task_status"], "SUCCESS")
        self.assertEqual(profile["pdf"]["task_status"], "SUCCESS")
        self.assertEqual(profile["github"]["task_status"], "SUCCESS")
        self.assertEqual(bot_call["tg_id"], "12345")
        self.assertIn(("parser", "processing"), stages)
        self.assertIn(("parser", "done"), stages)
        self.assertIn(("scoring", "processing"), stages)
        self.assertIn(("scoring", "done"), stages)
        self.assertIn(("notification", "processing"), stages)
        self.assertIn(("notification", "done"), stages)
        self.assertIn("candidate_profile", result)

    async def test_workflow_continues_scoring_when_parser_returns_completed_with_errors(self) -> None:
        workflow = CandidateWorkflow(
            {
                "bot": "http://bot",
                "scoring": "http://scoring",
                "parser": "http://parser",
            }
        )

        recorded_calls: list[tuple[str, dict]] = []

        async def fake_parser_request(endpoint: str, payload: dict):
            recorded_calls.append((f"parser:{endpoint}", payload))
            return {
                "status": "completed_with_errors",
                "summary": {
                    "requested_tasks": 3,
                    "success_count": 2,
                    "failure_count": 1,
                },
                "results": {
                    "essay_task": {
                        "status": "SUCCESS",
                        "result": {
                            "analysis": {
                                "scores": {
                                    "growth_mindset": 8,
                                    "resilience": 8,
                                    "motivation_clarity": 7,
                                    "mission_alignment": 7,
                                    "authenticity_confidence": 8,
                                }
                            },
                            "llm_parsed_ok": True,
                        },
                    },
                    "video_task": {
                        "status": "SUCCESS",
                        "result": {
                            "transcript": {"available": True, "source": "youtube_captions"},
                            "analysis": {
                                "signals": {
                                    "intrinsic": {"signals": {"mastery_mentions": ["learn"], "autonomy_mentions": ["build"]}},
                                    "mission_alignment": {"signal_count": 2},
                                },
                                "question_coverage": [{"question_id": "q5_leadership", "coverage_level": "partial"}],
                                "question_coverage_ratio": 0.7,
                            },
                        },
                    },
                    "file_task": {
                        "status": "FAILURE",
                        "error": "file_url did not return a PDF document",
                        "error_type": "ValueError",
                    },
                },
            }

        async def fake_scoring_request(endpoint: str, payload: dict):
            recorded_calls.append((f"scoring:{endpoint}", payload))
            return {"status": "success", "data": {"persistence": {"saved": True}}}

        workflow.parser_pipeline.send_request = fake_parser_request
        workflow.scoring_pipeline.send_request = fake_scoring_request

        stages: list[tuple[str, str]] = []
        result = await workflow.process_form_submission(
            {
                "candidate_id": "7",
                "Name": "Aruzhan",
                "Surname": "Sapar",
                "Personal Presentation (Undergraduate)": "https://youtu.be/example123",
                "Additional documents": "https://drive.google.com/file/d/test-pdf/view",
                "Reflect on a situation where your efforts or plan significantly failed. How exactly did you analyze what happened, and what new strategy did you choose to move forward? (Max characters: 100)": "I reflected and improved.",
                'The concept of "Jas Ulan" here means consistent readiness to update your knowledge and skills. Describe a skill, experience or issue in your life that currently is "outdated" for you. How exactly are you challenging yourself to improve it? (Max characters: 120)': "I keep improving with real projects.",
            },
            stage_callback=lambda stage, status, detail=None: stages.append((stage, status)),
        )

        scoring_call = next(payload for name, payload in recorded_calls if name == "scoring:evaluate")
        self.assertEqual(result["candidate_profile"]["pdf"]["task_status"], "FAILURE")
        self.assertEqual(
            result["candidate_profile"]["pdf"]["error"],
            "file_url did not return a PDF document",
        )
        self.assertIn("candidate_profile", scoring_call)
        self.assertIn(("parser", "partial"), stages)
        self.assertIn(("scoring", "processing"), stages)
        self.assertIn(("scoring", "done"), stages)


class ApiSmokeTests(unittest.TestCase):
    def test_parser_api_accepts_file_url_without_file_id(self) -> None:
        recorded: dict[str, object] = {}

        def fake_queue_tasks(**kwargs):
            recorded.update(kwargs)
            return {"status": "completed", "results": {}}

        client = TestClient(parser_main.api)
        with patch.object(parser_main.parser_service, "queue_tasks", side_effect=fake_queue_tasks):
            response = client.post(
                "/parse",
                json={"user_id": "11", "file_url": "https://example.com/resume.pdf"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(recorded["file_url"]), "https://example.com/resume.pdf")
        self.assertEqual(recorded["user_id"], "11")

    def test_parser_api_rejects_empty_parse_request(self) -> None:
        client = TestClient(parser_main.api)
        response = client.post("/parse", json={"user_id": "11"})
        self.assertEqual(response.status_code, 422)

    def test_scoring_api_persists_score_to_database(self) -> None:
        with temp_database() as temp_db, patch_module_dbs(temp_db, "services.scoring.service"):
            user_id = temp_db.upsert_user("tg_score_api")
            client = TestClient(scoring_main.api)

            response = client.post(
                "/evaluate",
                json={
                    "candidate_id": str(user_id),
                    "candidate_profile": {
                        "form": {"raw": {"Name": "Aruzhan", "Surname": "Sapar"}},
                        "essay": {
                            "llm_parsed_ok": True,
                            "analysis": {
                                "scores": {
                                    "growth_mindset": 7,
                                    "resilience": 7,
                                    "motivation_clarity": 8,
                                    "mission_alignment": 8,
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
                                        "intrinsic": {"signals": {"mastery_mentions": ["learn"], "autonomy_mentions": ["build"]}},
                                        "mission_alignment": {"signal_count": 3},
                                    },
                                    "question_coverage": [{"question_id": "q5_leadership", "coverage_level": "partial"}],
                                    "question_coverage_ratio": 0.8,
                                },
                            },
                        },
                        "pdf": {"task_status": "UNAVAILABLE", "data": {}},
                        "github": {"task_status": "UNAVAILABLE", "data": {}},
                    },
                },
            )

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["status"], "success")
            self.assertTrue(body["data"]["persistence"]["saved"])

            with temp_db._connect() as conn:
                score_row = conn.execute("SELECT * FROM scores WHERE user_id=?", (user_id,)).fetchone()
                audit_row = conn.execute("SELECT * FROM audit_log WHERE user_id=?", (user_id,)).fetchone()

            self.assertIsNotNone(score_row)
            self.assertIsNotNone(audit_row)


if __name__ == "__main__":
    unittest.main()
