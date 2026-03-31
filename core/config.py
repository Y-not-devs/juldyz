from dotenv import load_dotenv
import os

# Load environment variables from a .env file
load_dotenv()

# Telegram Bot Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Microservice Configuration
SERVICES = {
    "form-service": {
        "prefix": "/form-service",
        "url": os.getenv("FORM_SERVICE_URL", "http://localhost"),
        "port": int(os.getenv("FORM_SERVICE_PORT", 8001)),
        "log_level": os.getenv("FORM_SERVICE_LOG_LEVEL", "info"),
    },
    "bot-service": {
        "prefix": "/bot-service",
        "url": os.getenv("BOT_SERVICE_URL", "http://localhost"),
        "port": int(os.getenv("BOT_SERVICE_PORT", 8002)),
        "log_level": os.getenv("BOT_SERVICE_LOG_LEVEL", "info"),
    },
    "scoring-service": {
        "prefix": "/scoring-service",
        "url": os.getenv("SCORING_SERVICE_URL", "http://localhost"),
        "port": int(os.getenv("SCORING_SERVICE_PORT", 8003)),
        "log_level": os.getenv("SCORING_SERVICE_LOG_LEVEL", "info"),
    },
    "parser-service": {
        "prefix": "/parser-service",
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