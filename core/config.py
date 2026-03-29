from dotenv import load_dotenv
import os

load_dotenv()

TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
BOT_SERVICE_URL   = os.getenv("BOT_SERVICE_URL", "http://localhost:8002")
FORM_API          = os.getenv("FORM_API", "http://localhost:8000")
FORM_URL          = os.getenv("FORM_URL")
TG_ID_FIELD       = os.getenv("TG_ID_FIELD")