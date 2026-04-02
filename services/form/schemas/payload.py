from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class FormSubmitRequest(BaseModel):
    tg_id: str = Field(..., description="Telegram ID of the candidate")
    # Optional: allow any extra fields in the form payload
    data: Optional[Dict[str, Any]] = Field(default_factory=dict)

class FormSubmitResponse(BaseModel):
    status: str
    candidate_id: Optional[str] = None
    detail: Optional[str] = None