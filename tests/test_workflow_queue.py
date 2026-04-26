from __future__ import annotations

import gc
import sys
import tempfile
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
project_root_str = str(PROJECT_ROOT)
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from core.db import Database


class WorkflowQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self._tmpdir.name) / "queue_test.db")
        self.user_id = self.db.upsert_user("tg_queue_test")

    def tearDown(self) -> None:
        db_path = Path(self.db.path)
        del self.db
        gc.collect()
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(f"{db_path}{suffix}")
            if not candidate.exists():
                continue
            for _ in range(20):
                try:
                    candidate.unlink()
                    break
                except PermissionError:
                    gc.collect()
                    time.sleep(0.1)
                except FileNotFoundError:
                    break
        try:
            self._tmpdir.cleanup()
        except PermissionError:
            pass

    def test_workflow_job_retries_then_dead_letters(self) -> None:
        response_id = self.db.save_candidate_response(
            self.user_id,
            {"Name": "Queue", "Surname": "Candidate"},
        )
        job_id = self.db.enqueue_workflow_job(
            response_id=response_id,
            user_id=self.user_id,
            payload={"tg_id": "tg_queue_test", "Name": "Queue"},
            max_attempts=2,
        )

        claimed_first = self.db.claim_next_workflow_job()
        self.assertIsNotNone(claimed_first)
        self.assertEqual(claimed_first["id"], job_id)
        self.assertEqual(claimed_first["status"], "processing")
        self.assertEqual(claimed_first["attempts"], 1)

        retry_job = self.db.fail_workflow_job(job_id, "boom", retry_delay_seconds=1)
        self.assertEqual(retry_job["status"], "retry")

        time.sleep(1.1)

        claimed_second = self.db.claim_next_workflow_job()
        self.assertIsNotNone(claimed_second)
        self.assertEqual(claimed_second["id"], job_id)
        self.assertEqual(claimed_second["attempts"], 2)

        dead_job = self.db.fail_workflow_job(job_id, "boom again", retry_delay_seconds=1)
        self.assertEqual(dead_job["status"], "dead_letter")
        self.assertEqual(dead_job["current_stage"], "dead_letter")

    def test_recover_stale_workflow_job_marks_current_stage_failed_for_retry(self) -> None:
        response_id = self.db.save_candidate_response(
            self.user_id,
            {"Name": "Stale", "Surname": "Candidate"},
        )
        job_id = self.db.enqueue_workflow_job(
            response_id=response_id,
            user_id=self.user_id,
            payload={"tg_id": "tg_queue_test", "Name": "Stale"},
            max_attempts=3,
        )
        self.db.claim_next_workflow_job()

        with self.db._connect() as conn:
            conn.execute(
                """
                UPDATE workflow_jobs
                SET current_stage='parser',
                    locked_at=datetime('now', '-3600 seconds')
                WHERE id=?
                """,
                (job_id,),
            )
            conn.execute(
                """
                UPDATE candidate_responses
                SET parser_status='processing'
                WHERE id=?
                """,
                (response_id,),
            )

        recovered = self.db.recover_stale_workflow_jobs(timeout_seconds=10)
        self.assertEqual(recovered, 1)

        saved_response = self.db.get_candidate_response_by_id(response_id)
        self.assertEqual(saved_response["processing_status"], "pending")
        self.assertEqual(saved_response["parser_status"], "failed")
        self.assertIn("timed out", saved_response["parser_error"])

    def test_enqueue_existing_workflow_job_resets_attempts(self) -> None:
        response_id = self.db.save_candidate_response(
            self.user_id,
            {"Name": "Requeue", "Surname": "Candidate"},
        )
        job_id = self.db.enqueue_workflow_job(
            response_id=response_id,
            user_id=self.user_id,
            payload={"tg_id": "tg_queue_test", "Name": "Requeue"},
            max_attempts=2,
        )
        self.db.claim_next_workflow_job()
        self.db.fail_workflow_job(job_id, "boom", retry_delay_seconds=1)

        self.db.enqueue_workflow_job(
            response_id=response_id,
            user_id=self.user_id,
            payload={"tg_id": "tg_queue_test", "Name": "Requeue again"},
            max_attempts=3,
        )

        with self.db._connect() as conn:
            saved_job = conn.execute("SELECT * FROM workflow_jobs WHERE id=?", (job_id,)).fetchone()
        self.assertEqual(saved_job["attempts"], 0)
        self.assertEqual(saved_job["status"], "queued")

    def test_update_candidate_response_stage_accepts_partial_status(self) -> None:
        response_id = self.db.save_candidate_response(
            self.user_id,
            {"Name": "Partial", "Surname": "Candidate"},
        )

        self.db.update_candidate_response_stage(
            response_id,
            "parser",
            "partial",
            "parser completed_with_errors: {'failure_count': 1}",
        )

        saved_response = self.db.get_candidate_response_by_id(response_id)
        self.assertEqual(saved_response["parser_status"], "partial")
        self.assertIn("completed_with_errors", saved_response["parser_error"])


if __name__ == "__main__":
    unittest.main()
