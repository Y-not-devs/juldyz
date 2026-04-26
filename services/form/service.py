from core.db import db


class FormService:
    @staticmethod
    def get_candidate(tg_id: str):
        return db.get_user_by_tg(tg_id)

    @staticmethod
    def save_response(candidate_id: str, payload: dict):
        return db.save_candidate_response(candidate_id, payload)

    @staticmethod
    def mark_response_pending(response_id: int):
        db.update_candidate_response_processing(response_id, "pending")

    @staticmethod
    def mark_response_processing(response_id: int):
        db.update_candidate_response_processing(response_id, "processing")

    @staticmethod
    def mark_response_done(response_id: int):
        db.update_candidate_response_processing(response_id, "done")

    @staticmethod
    def mark_response_failed(response_id: int, error: str):
        db.update_candidate_response_processing(response_id, "failed", error)

    @staticmethod
    def update_stage_status(response_id: int, stage: str, status: str, error: str | None = None):
        db.update_candidate_response_stage(response_id, stage, status, error)

    @staticmethod
    def reset_response_stages(response_id: int):
        db.reset_candidate_response_stages(response_id)

    @staticmethod
    def enqueue_workflow_job(response_id: int, candidate_id: int, payload: dict, max_attempts: int = 3):
        return db.enqueue_workflow_job(response_id, candidate_id, payload, max_attempts=max_attempts)

    @staticmethod
    def claim_next_workflow_job():
        return db.claim_next_workflow_job()

    @staticmethod
    def recover_stale_workflow_jobs(timeout_seconds: int = 900):
        return db.recover_stale_workflow_jobs(timeout_seconds=timeout_seconds)

    @staticmethod
    def update_workflow_job_stage(job_id: int, stage: str):
        db.update_workflow_job_stage(job_id, stage)

    @staticmethod
    def get_workflow_job(job_id: int):
        return db.get_workflow_job(job_id)

    @staticmethod
    def complete_workflow_job(job_id: int):
        db.complete_workflow_job(job_id)

    @staticmethod
    def fail_workflow_job(job_id: int, error: str, retry_delay_seconds: int = 30):
        return db.fail_workflow_job(job_id, error, retry_delay_seconds=retry_delay_seconds)
