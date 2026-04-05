import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from pydantic import BaseModel
import uvicorn
from core.db import db
from core.config import TELEGRAM_TOKEN, GOOGLE_FORM_URL, QUESTION_FIELD_ID, SERVICES
from services.bot.service import BotService
from services.bot.schemas.notify import NotifyRequest

bot_service = BotService(
    db=db,
    TELEGRAM_TOKEN=TELEGRAM_TOKEN,
    GOOGLE_FORM_URL=GOOGLE_FORM_URL,
    QUESTION_FIELD_ID=QUESTION_FIELD_ID
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start polling as a background task in uvicorn's event loop
    polling_task = asyncio.create_task(bot_service.start_polling())
    yield
    # Graceful shutdown
    polling_task.cancel()
    try:
        await polling_task
    except asyncio.CancelledError:
        pass

api = FastAPI(lifespan=lifespan)
router = APIRouter(tags=["bot-service"])


class SendRequest(BaseModel):
    candidate_id: str
    text: str


@router.post("/notify")
async def notify(data: NotifyRequest):
    await bot_service.notify_user(data.tg_id)
    return {"status": "ok"}


@router.post("/send")
async def send(data: SendRequest):
    await bot_service.send_message(data.candidate_id, data.text)
    return {"status": "ok"}

@router.get("/health")
async def health():
    return {"status": "ok", "service": "bot"}

api.include_router(router)

if __name__ == "__main__":
    cfg = SERVICES['bot-service']
    uvicorn.run(api, host=cfg['url'], port=cfg['port'], log_level=cfg['log_level'])
