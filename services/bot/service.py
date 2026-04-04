from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from core.db import db

class BotService:
    def __init__(self, db, TELEGRAM_TOKEN, GOOGLE_FORM_URL, QUESTION_FIELD_ID):
        self.bot = Bot(token=TELEGRAM_TOKEN)
        self.dp = Dispatcher()
        self.db = db
        self.google_form_url = GOOGLE_FORM_URL
        self.question_field_id = QUESTION_FIELD_ID
        self._register_handlers()

    def _register_handlers(self):
        @self.dp.message(CommandStart())
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

            form_link = f"{self.google_form_url}?usp=pp_url&entry.{self.question_field_id}={tg_id}"
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="📋 Заполнить анкету", url=form_link)
            ]])
            await message.answer(
                f"Привет, {message.from_user.first_name}! 👋\n\n"
                f"Это система отбора кандидатов inVision U.\n\n"
                f"Нажми кнопку ниже чтобы заполнить анкету.",
                reply_markup=kb
            )

    async def notify_user(self, tg_id: str):
        await self.bot.send_message(
            chat_id=int(tg_id),
            text="✅ Анкета получена! Мы свяжемся с тобой."
        )

    async def start_polling(self):
        await self.dp.start_polling(self.bot, handle_signals=False)