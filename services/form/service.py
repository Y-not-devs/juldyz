from core.db import db

class FormService:
    @staticmethod
    def get_candidate(tg_id: str):
        return db.get_user_by_tg(tg_id)

    @staticmethod
    def save_response(candidate_id: str, payload: dict):
        db.save_candidate_response(candidate_id, payload)
