from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any

class FormSubmitRequest(BaseModel):
    model_config = ConfigDict(extra='allow')
    
    tg_id: str = Field(..., description="Telegram ID of the candidate")
    data: Optional[Dict[str, Any]] = Field(default_factory=dict)

class FormSubmitResponse(BaseModel):
    status: str
    candidate_id: Optional[str] = None
    detail: Optional[str] = None