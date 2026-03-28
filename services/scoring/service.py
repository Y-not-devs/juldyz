# services/scoring/service.py
from core.db import SessionLocal
from core.repository import UserRepository


class ScoringService:
    def __init__(self):
        self.db = SessionLocal()
        self.user_repo = UserRepository(self.db)

    def calculate_score(self, user_id: int):
        user = self.user_repo.get_user(user_id)

        if not user:
            return 0

        # пример логики
        score = len(user.name) * 10
        return score