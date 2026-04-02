from pydantic import BaseModel


class LLMGenerateRequest(BaseModel):
    instruction: str
    text: str


class LLMGenerateResponse(BaseModel):
    task_id: str


class LLMTaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: str | None = None
