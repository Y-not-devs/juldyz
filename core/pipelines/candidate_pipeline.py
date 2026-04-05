from __future__ import annotations

from typing import Any

from core.clients import BotClient, ParserClient, ScoringClient


class CandidatePipeline:
    def __init__(
        self,
        parser_client: ParserClient,
        scoring_client: ScoringClient,
        bot_client: BotClient,
    ):
        self._parser = parser_client
        self._scoring = scoring_client
        self._bot = bot_client

    @staticmethod
    def _extract_youtube_url(form_payload: dict[str, Any]) -> str | None:
        candidates = [
            form_payload.get("youtube_url"),
            form_payload.get("video_url"),
            form_payload.get("personal_presentation"),
            form_payload.get("Personal Presentation (Foundation)"),
            form_payload.get("Personal Presentation (Undergraduate)"),
        ]
        for value in candidates:
            if isinstance(value, str):
                cleaned = value.strip()
                if "youtube.com" in cleaned or "youtu.be" in cleaned:
                    return cleaned
        return None

    async def run(self, candidate_id: str, form_payload: dict[str, Any]) -> dict[str, Any]:
        youtube_url = self._extract_youtube_url(form_payload)
        parse_result = await self._parser.parse(
            user_id=candidate_id,
            file_id=form_payload.get("file_id"),
            github_url=form_payload.get("github_url"),
            youtube_url=youtube_url,
        )
        if parse_result.get("mode") == "direct":
            parser_wait_result = {
                "completed": parse_result.get("results", {}),
                "timed_out": [],
            }
        else:
            parser_tasks = {
                "github_task": parse_result.get("github_task_id"),
                "file_task": parse_result.get("file_task_id"),
                "video_task": parse_result.get("video_task_id"),
            }
            parser_wait_result = await self._parser.wait_for_tasks(parser_tasks)

        scoring_input = {
            "candidate_id": candidate_id,
            "form_data": form_payload,
            "parser_context": {
                "queue": parse_result,
                "results": parser_wait_result.get("completed", {}),
                "timed_out": parser_wait_result.get("timed_out", []),
            },
            "essay": form_payload.get("essay", ""),
        }
        score_result = await self._scoring.evaluate(scoring_input)

        tg_id = str(form_payload.get("tg_id", "")).strip()
        notification_result = None
        if tg_id:
            notification_result = await self._bot.notify(tg_id=tg_id, candidate_id=candidate_id)

        return {
            "pipeline": "candidate",
            "candidate_id": candidate_id,
            "parse": parse_result,
            "parse_results": parser_wait_result,
            "score": score_result,
            "notify": notification_result,
        }
