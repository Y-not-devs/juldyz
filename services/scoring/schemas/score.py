from pydantic import BaseModel

class CandidateScore(BaseModel):
    candidate_id: str | None = None
    score: float | None = None