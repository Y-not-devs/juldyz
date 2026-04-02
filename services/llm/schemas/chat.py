from pydantic import BaseModel

class LLM_Request(BaseModel):
    request_id: str
    prompt: str
    message: str
    language: str

class LLM_Response(BaseModel):
    request_id: str
    response: str
    model: str