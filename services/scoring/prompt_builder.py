
from .config import settings


def build_messages(messages):
    return [
        {"role": "system", "content": settings.SYSTEM_PROMPT},
        *[m.dict() for m in messages]
    ]