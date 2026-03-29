from core.logger import setup_logging
setup_logging("bot")


import asyncio
import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from core.config import TELEGRAM_TOKEN, FORM_URL
from core.db import db
print(f"[BOT] loaded config: TELEGRAM_TOKEN={TELEGRAM_TOKEN} FORM_URL={FORM_URL}")
bot = Bot(token=str(TELEGRAM_TOKEN))
dp  = Dispatcher()
api = FastAPI(title="bot-service")


# --- Telegram handlers ---

@dp.message(CommandStart())
async def start(message: Message):
    tg_id = str(message.from_user.id)

    db.upsert_user(telegram_id=tg_id)
    db.upsert_telegram_user(
        telegram_id=tg_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        language_code=message.from_user.language_code,
        is_bot=message.from_user.is_bot,
        raw=message.from_user.model_dump()
    )

    form_link = f"{FORM_URL}?entry.TG_ID_FIELD={tg_id}"

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📋 Заполнить анкету", url=form_link)
    ]])

    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        f"Это система отбора кандидатов inVision U.\n\n"
        f"Нажми кнопку ниже чтобы заполнить анкету.\n"
        f"После отправки я пришлю подтверждение.",
        reply_markup=kb
    )

    print(f"[BOT] /start tg_id={tg_id}")


# --- Internal API (called by form-service) ---

@api.post("/notify")
async def notify(data: dict):
    tg_id        = data.get("tg_id")
    candidate_id = data.get("candidate_id")

    if not tg_id:
        return JSONResponse({"status": "error", "detail": "no tg_id"}, status_code=400)

    await bot.send_message(
        chat_id=int(tg_id),
        text=(
            "✅ Анкета получена!\n\n"
            "Мы изучим твою заявку и свяжемся с тобой в ближайшее время.\n"
            "Следи за обновлениями здесь."
        )
    )

    print(f"[BOT] notified tg_id={tg_id} candidate_id={candidate_id}")
    return JSONResponse({"status": "ok"})


@api.get("/health")
def health():
    return {"status": "ok", "service": "bot"}


# --- Entry point ---

async def main():
    config = uvicorn.Config(api, host="0.0.0.0", port=8002, log_level="warning")
    server = uvicorn.Server(config)

    print("[BOT] starting polling + api on :8002")
    await asyncio.gather(
        dp.start_polling(bot),
        server.serve()
    )


if __name__ == "__main__":
    asyncio.run(main())
