import json
import asyncio
from services.scoring.schemas.score import CandidateScore

class ScoringService:
    def __init__(self):
        pass

    async def evaluate_candidate(self, candidate_data: dict) -> dict:
        """
        Мок-оценка кандидата без вызова внешних сервисов (LLM/Parser).
        """
        # Имитация задержки (как будто работает тяжелая нейросеть)
        await asyncio.sleep(2)
        
        # Читаем данные из запроса для минимальной реалистичности
        essay = str(candidate_data.get("essay", "")).lower()
        github_stats = candidate_data.get("github_stats", {})
        
        # Примитивная логика скоринга для демо-видео
        score_leadership = 8 if "стартап" in essay or "проект" in essay else 5
        score_motivation = 9 if "инноваци" in essay or "университет" in essay else 7
        
        commits = github_stats.get("total_commits", 0) if isinstance(github_stats, dict) else 0
        score_exp = min(10, (commits // 50) + 4) if commits > 0 else 5
        
        # Собираем результат, идеально подходящий под ТЗ хакатона
        return {
            "scores": {
                "leadership": score_leadership,
                "experience": score_exp,
                "motivation": score_motivation,
                "authenticity": 8 # Фейкова метрика "написано ли это через ChatGPT"
            },
            "overall_score": round((score_leadership + score_exp + score_motivation + 8) / 4, 1),
            "explanation": "Кандидат обладает базовым опытом. Выявлены лидерские задатки благодаря упомянутому опыту ведения собственных проектов. Эссе выглядит аутентично.",
            "red_flags": ["Мало профильной активности" if commits < 10 else ""],
            "green_flags": ["Инициативность", "Есть пет-проекты"]
        }

