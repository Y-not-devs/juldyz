from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    OLLAMA_URL: str = "http://localhost:11434"
    MODEL_NAME: str = "qwen2.5:7b-instruct"

    DEFAULT_TEMPERATURE: float = 0.7
    DEFAULT_TOP_P: float = 0.9

    SYSTEM_PROMPT: str = "Ты полезный AI ассистент"

settings = Settings()