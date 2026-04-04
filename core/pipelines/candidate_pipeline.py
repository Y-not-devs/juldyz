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

    async def run(self, candidate_id: str, form_payload: dict[str, Any]) -> dict[str, Any]:
        parse_result = await self._parser.parse(
            user_id=candidate_id,
            file_id=form_payload.get("file_id"),
            github_url=form_payload.get("github_url"),
        )

        scoring_input = {
            "candidate_id": candidate_id,
            "form_data": form_payload,
            "parser_context": parse_result,
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
            "score": score_result,
            "notify": notification_result,
        }
