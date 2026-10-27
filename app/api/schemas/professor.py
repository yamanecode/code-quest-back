from pydantic import BaseModel, ConfigDict

from app.api.schemas.classrooms import GoalOut


class ClassroomIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    weekly_goal: int | None = None


class ClassroomOut(BaseModel):
    id: int
    name: str
    join_code: str
    weekly_goal: int | None
    closed: bool
    goal: GoalOut | None


class MissionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str | None = None
    position: int | None = None


class MissionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str | None = None
    position: int


class MissionOrderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission_ids: list[int]


class MissionChallengesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenge_ids: list[int]


class ChallengeRefOut(BaseModel):
    id: int
    title: str
    type: str
    status: str


class MissionOut(BaseModel):
    id: int
    classroom_id: int
    title: str
    description: str | None
    position: int
    status: str
    challenges: list[ChallengeRefOut]


class ChallengeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    statement: str
    type: str
    content: dict
    explanation: str | None = None


class SolveStatsOut(BaseModel):
    attempted: int
    solved: int


class ChallengeOut(BaseModel):
    """Full professor view, solution included; never used for students."""

    id: int
    title: str
    statement: str
    type: str
    skill: str
    content: dict
    explanation: str | None
    status: str
    origin: str
    locked: bool
    solve_stats: SolveStatsOut


class ReviewOut(BaseModel):
    rule_violations: list[str]
    suggestions: str


class DraftIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    topic: str
    mission_id: int | None = None
