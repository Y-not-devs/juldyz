from pydantic import BaseModel
from typing import List


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    temperature: float | None = None
    top_p: float | None = None


class ChatResponse(BaseModel):
    response: str