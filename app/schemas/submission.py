from typing import Any

from pydantic import BaseModel


class SubmissionCreate(BaseModel):
    challenge_id: int
    answer: dict[str, Any]


class SubmissionResponse(BaseModel):
    id: int
    challenge_id: int
    is_correct: bool
    xp_earned: int
    attempt_number: int
    ai_feedback: str | None

    class Config:
        from_attributes = True
