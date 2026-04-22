from dotenv import load_dotenv
import os

load_dotenv()

def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

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
        "mode": int(os.getenv("LLM_MODE", 1)), 
    },
}

GOOGLE_FORM_URL = os.getenv("GOOGLE_FORM_URL")
QUESTION_FIELD_ID = os.getenv("QUESTION_FIELD_ID")

GOOGLE_DRIVE_BEARER_TOKEN = os.getenv("GOOGLE_DRIVE_BEARER_TOKEN")
GOOGLE_DRIVE_COOKIE = os.getenv("GOOGLE_DRIVE_COOKIE")
GOOGLE_DRIVE_DOWNLOAD_TIMEOUT_SECONDS = _float_env("GOOGLE_DRIVE_DOWNLOAD_TIMEOUT_SECONDS", 90.0)
                              
GATEWAY_HOST = os.getenv("GATEWAY_HOST", "0.0.0.0")
GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", 8000))
LOG_LEVEL = os.getenv("LOG_LEVEL", "info")

HTTP_CONNECT_TIMEOUT_SECONDS = _float_env("HTTP_CONNECT_TIMEOUT_SECONDS", 5.0)
HTTP_WRITE_TIMEOUT_SECONDS = _float_env("HTTP_WRITE_TIMEOUT_SECONDS", 30.0)
HTTP_POOL_TIMEOUT_SECONDS = _float_env("HTTP_POOL_TIMEOUT_SECONDS", 10.0)

ORCHESTRATOR_SERVICE_READ_TIMEOUT_SECONDS = {
    "bot-service": _float_env("ORCHESTRATOR_BOT_READ_TIMEOUT_SECONDS", 20.0),
    "scoring-service": _float_env("ORCHESTRATOR_SCORING_READ_TIMEOUT_SECONDS", 60.0),
    "parser-service": _float_env("ORCHESTRATOR_PARSER_READ_TIMEOUT_SECONDS", 420.0),
}

GATEWAY_PROXY_READ_TIMEOUT_SECONDS = {
    "form-service": _float_env("GATEWAY_FORM_READ_TIMEOUT_SECONDS", 30.0),
    "bot-service": _float_env("GATEWAY_BOT_READ_TIMEOUT_SECONDS", 20.0),
    "scoring-service": _float_env("GATEWAY_SCORING_READ_TIMEOUT_SECONDS", 60.0),
    "parser-service": _float_env("GATEWAY_PARSER_READ_TIMEOUT_SECONDS", 420.0),
    "llm-service": _float_env("GATEWAY_LLM_READ_TIMEOUT_SECONDS", 240.0),
    "dashboard-service": _float_env("GATEWAY_DASHBOARD_READ_TIMEOUT_SECONDS", 30.0),
}

DASHBOARD_REQUEST_TIMEOUT_SECONDS = {
    "bot": _float_env("DASHBOARD_BOT_TIMEOUT_SECONDS", GATEWAY_PROXY_READ_TIMEOUT_SECONDS["bot-service"]),
    "parser": _float_env("DASHBOARD_PARSER_TIMEOUT_SECONDS", GATEWAY_PROXY_READ_TIMEOUT_SECONDS["parser-service"]),
    "scoring": _float_env("DASHBOARD_SCORING_TIMEOUT_SECONDS", GATEWAY_PROXY_READ_TIMEOUT_SECONDS["scoring-service"]),
}

LLM_GENERATE_TIMEOUT_SECONDS = _float_env("LLM_GENERATE_TIMEOUT_SECONDS", 180.0)
FORM_WORKFLOW_MAX_CONCURRENT_JOBS = max(1, _int_env("FORM_WORKFLOW_MAX_CONCURRENT_JOBS", 4))

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
REDIS_DATA_DIR = os.getenv("REDIS_DATA_DIR", "./data/redis")

REDIS_URL = os.getenv(
    "REDIS_URL",
    f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
)

CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL",
    REDIS_URL
)

CELERY_RESULT_BACKEND = os.getenv(
    "CELERY_RESULT_BACKEND",
    f"redis://{REDIS_HOST}:{REDIS_PORT}/1"
)
