from dotenv import load_dotenv
import os

# Load environment variables from a .env file
load_dotenv()

# Telegram Bot Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Microservice Configuration
SERVICES = {
    "form-service": {
        "prefix": "form-service",
        "script": "services/form/main.py",
        "url": os.getenv("FORM_SERVICE_URL", "http://localhost"),
        "port": int(os.getenv("FORM_SERVICE_PORT", 8001)),
        "log_level": os.getenv("FORM_SERVICE_LOG_LEVEL", "info"),
    },
    "bot-service": {
        "prefix": "bot-service",
        "script": "services/bot/main.py",
        "url": os.getenv("BOT_SERVICE_URL", "http://localhost"),
        "port": int(os.getenv("BOT_SERVICE_PORT", 8002)),
        "log_level": os.getenv("BOT_SERVICE_LOG_LEVEL", "info"),
    },
    "scoring-service": {
        "prefix": "scoring-service",
        "script": "services/scoring/main.py",
        "url": os.getenv("SCORING_SERVICE_URL", "http://localhost"),
        "port": int(os.getenv("SCORING_SERVICE_PORT", 8003)),
        "log_level": os.getenv("SCORING_SERVICE_LOG_LEVEL", "info"),
    },
    "parser-service": {
        "prefix": "parser-service",
        "script": "services/parser/main.py",
        "url": os.getenv("PARSER_SERVICE_URL", "http://localhost"),
        "port": int(os.getenv("PARSER_SERVICE_PORT", 8004)),
        "log_level": os.getenv("PARSER_SERVICE_LOG_LEVEL", "info"),
    },
}

# Google Form URL
GOOGLE_FORM_URL = os.getenv("GOOGLE_FORM_URL")
QUESTION_FIELD_ID = os.getenv("QUESTION_FIELD_ID")
                              
# Gateway Configuration
GATEWAY_HOST = os.getenv("GATEWAY_HOST", "0.0.0.0")
GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", 8000))
LOG_LEVEL = os.getenv("LOG_LEVEL", "info")

# Redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
REDIS_DATA_DIR = os.getenv("REDIS_DATA_DIR", "./data/redis")

REDIS_URL = os.getenv(
    "REDIS_URL",
    f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
)

# Celery
CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL",
    REDIS_URL
)

CELERY_RESULT_BACKEND = os.getenv(
    "CELERY_RESULT_BACKEND",
    f"redis://{REDIS_HOST}:{REDIS_PORT}/1"
)