from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MissionSummaryOut(BaseModel):
    id: int
    title: str
    description: str | None
    total: int
    solved: int


class ClassroomMissionsOut(BaseModel):
    id: int
    name: str
    missions: list[MissionSummaryOut]


class MissionsOut(BaseModel):
    base: list[MissionSummaryOut]
    classrooms: list[ClassroomMissionsOut]


class ChallengeSummaryOut(BaseModel):
    id: int
    title: str
    type: str
    skill: str
    solved: bool


class MissionDetailOut(BaseModel):
    id: int
    title: str
    description: str | None
    challenges: list[ChallengeSummaryOut]


class ChallengeForStudentOut(BaseModel):
    """Student view of a challenge: never carries the solution or the explanation."""

    id: int
    title: str
    statement: str
    type: str
    skill: str
    content: dict
    solved: bool
    hints_left: int
    cooldown_seconds_left: int


class HintOut(BaseModel):
    hint: str
    level: int
    hints_left: int
    cooldown_seconds: int


class SubmissionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: dict


class NewBadgeOut(BaseModel):
    code: str
    name: str
    description: str
    tier: str
    emoji: str


class SubmissionOut(BaseModel):
    is_correct: bool
    xp_earned: int
    xp: int
    level: int
    title: str
    level_up: bool
    new_badges: list[NewBadgeOut]
    explanation: str | None
    hint: str | None


class DailyOut(BaseModel):
    challenge: ChallengeSummaryOut | None
    all_solved: bool


class ProfileBadgeOut(BaseModel):
    code: str
    name: str
    description: str
    tier: str
    emoji: str
    hidden: bool
    earned: bool
    earned_at: datetime | None


class ProfileOut(BaseModel):
    username: str
    role: str
    xp: int
    level: int
    title: str
    xp_to_next_level: int
    streak: int
    missions_completed: int
    solved_by_skill: dict[str, int]
    first_try_solves: int
    profile_public: bool
    badges: list[ProfileBadgeOut]


class SettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_public: bool


class SettingsOut(BaseModel):
    profile_public: bool
