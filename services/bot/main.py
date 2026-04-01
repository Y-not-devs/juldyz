import asyncio
import uvicorn
from fastapi import FastAPI, APIRouter

from core.logger import setup_logging
from core.config import TELEGRAM_TOKEN, GOOGLE_FORM_URL, QUESTION_FIELD_ID, SERVICES
from core.db import db
from services.bot.service import BotService
from services.bot.schemas.notify import NotifyRequest

setup_logging(SERVICES['bot-service']['prefix'])

api = FastAPI(title=f"{SERVICES['bot-service']['prefix']} API")
router = APIRouter(tags=["bot-service"])
bot_service = BotService(
    db=db,
    TELEGRAM_TOKEN=TELEGRAM_TOKEN,
    GOOGLE_FORM_URL=GOOGLE_FORM_URL,
    QUESTION_FIELD_ID=QUESTION_FIELD_ID
)

@router.post("/notify")
async def notify(data: NotifyRequest):
    await bot_service.notify_user(data.tg_id)
    return {"status": "ok"}

@router.get("/health")
async def health():
    return {"status": "ok", "service": "bot"}

api.include_router(router)

async def start_bot():
    await bot_service.start_polling()

# --- Entry point ---
async def main():
    cfg = SERVICES['bot-service']
    config = uvicorn.Config(
        api,
        host=cfg['url'],
        port=cfg['port'],
        log_level=cfg['log_level']
    )
    server = uvicorn.Server(config)

    print(f"[BOT] starting polling + api on :{cfg['port']}")
    await asyncio.gather(
        start_bot(),
        server.serve()
    )


if __name__ == "__main__":
    asyncio.run(main())