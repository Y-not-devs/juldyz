from pydantic import BaseModel, Field


class SystemEvent(BaseModel):
    type: str = Field(..., description="Event type identifier")
    payload: dict = Field(default_factory=dict, description="Event payload")
