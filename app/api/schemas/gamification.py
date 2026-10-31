from typing import Literal

from pydantic import BaseModel

RankingScopeIn = Literal["global", "classroom"]
RankingPeriodIn = Literal["week", "month"]


class RankingEntryOut(BaseModel):
    position: int
    username: str
    xp: int
    is_me: bool
    profile_public: bool


class RankingOut(BaseModel):
    scope: str
    period: str
    entries: list[RankingEntryOut]


class PublicBadgeOut(BaseModel):
    code: str
    name: str
    tier: str
    emoji: str


class PublicProfileOut(BaseModel):
    """Everything another player may see (SG-13); add nothing here."""

    username: str
    level: int
    title: str
    badges: list[PublicBadgeOut]


class StudentProgressOut(BaseModel):
    username: str
    xp_in_class: int
    level: int
    solved_in_class: int
    missions_completed_in_class: int
    hints_used: int


class ClassroomProgressOut(BaseModel):
    completed_all_pct: int
    students: list[StudentProgressOut]
