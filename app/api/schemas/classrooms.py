from datetime import date

from pydantic import BaseModel, ConfigDict


class JoinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    join_code: str


class ClassroomRefOut(BaseModel):
    id: int
    name: str


class GoalOut(BaseModel):
    target: int
    progress: int
    week_start: date
    completed: bool


class MyClassroomOut(BaseModel):
    id: int
    name: str
    goal: GoalOut | None
