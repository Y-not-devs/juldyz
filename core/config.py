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
    "dashboard-service": {
        "prefix": "dashboard-service",
        "script": "services/dashboard/main.py",
        "url": os.getenv("DASHBOARD_SERVICE_URL", "http://localhost"),
        "port": int(os.getenv("DASHBOARD_SERVICE_PORT", 8501)),
        "log_level": os.getenv("DASHBOARD_SERVICE_LOG_LEVEL", "info"),
        "page_port": int(os.getenv("DASHBOARD_SERVICE_PAGE_PORT", 8502)),
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
    "llm-service": {
        "prefix": "llm-service",
        "script": "services/llm/main.py",
        "url": os.getenv("LLM_SERVICE_URL", "http://localhost"),
        "port": int(os.getenv("LLM_SERVICE_PORT", 8005)),
        "log_level": os.getenv("LLM_SERVICE_LOG_LEVEL", "info"),
        "model_path": os.getenv("LLM_MODEL_PATH", "./models/qwen"),
        "hf_model_id": os.getenv("LLM_HF_MODEL_ID", "Qwen/Qwen2.5-1.5B-Instruct"),
        "hf_token": os.getenv("LLM_HF_TOKEN"),
        "mode": int(os.getenv("LLM_MODE", 1)),  # 0=offline, 1=auto_update, 2=token_update
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