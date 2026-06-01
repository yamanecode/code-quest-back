from pydantic import BaseModel
from enum import Enum
from typing import Any


class ChallengeType(str, Enum):
    steps = "steps"
    pattern = "pattern"
    algorithm = "algorithm"
    ordering = "ordering"
    abstraction = "abstraction"


class ChallengeCategory(str, Enum):
    decomposition = "decomposition"
    pattern = "pattern"
    abstraction = "abstraction"
    algorithm = "algorithm"


class ChallengeCreate(BaseModel):
    title: str
    description: str
    difficulty: int = 1
    category: ChallengeCategory
    type: ChallengeType
    content: dict[str, Any]
    is_daily: bool = False


class ChallengeResponse(BaseModel):
    id: int
    title: str
    description: str
    difficulty: int
    category: ChallengeCategory
    type: ChallengeType
    content: dict[str, Any]
    is_daily: bool

    class Config:
        from_attributes = True