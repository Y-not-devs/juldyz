from pydantic import BaseModel

class NotifyRequest(BaseModel):
    tg_id: str
    candidate_id: str | None = None