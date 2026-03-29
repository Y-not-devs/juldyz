
import requests
from .config import settings


class LLMService:

    def __init__(self):
        self.url = f"{settings.OLLAMA_URL}/api/chat"

    def chat(self, messages, temperature=None, top_p=None):
        payload = {
            "model": settings.MODEL_NAME,
            "messages": messages,
            "options": {
                "temperature": temperature or settings.DEFAULT_TEMPERATURE,
                "top_p": top_p or settings.DEFAULT_TOP_P,
            },
            "stream": False
        }

        response = requests.post(self.url, json=payload, timeout=60)

        response.raise_for_status()

        return response.json()["message"]["content"]


llm_service = LLMService()