from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MissionSummaryOut(BaseModel):
    id: int
    title: str
    description: str | None
    total: int
    solved: int
    is_new: bool
    has_new_challenges: bool


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
    is_new: bool


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
    is_new: bool
    explanation: str | None
    cooldown_seconds_left: int


class HintOut(BaseModel):
    hint: str
    level: int
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


class ContinueOut(BaseModel):
    mission_id: int
    mission_title: str
    challenge_id: int
    challenge_title: str
    is_new: bool


class ProfileBadgeOut(BaseModel):
    code: str
    name: str
    description: str
    tier: str
    emoji: str
    hidden: bool
    requires_class: bool
    earned: bool
    earned_at: datetime | None


class TitleStepOut(BaseModel):
    title: str
    min_level: int
    max_level: int | None


class ProfileOut(BaseModel):
    username: str
    role: str
    xp: int
    level: int
    title: str
    xp_to_next_level: int
    title_steps: list[TitleStepOut]
    missions_completed: int
    solved_by_skill: dict[str, int]
    first_try_solves: int
    profile_public: bool
    recovery_code_active: bool
    recovery_code_created_at: datetime | None
    recovery_code_confirmed: bool
    badges: list[ProfileBadgeOut]


class SettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_public: bool


class SettingsOut(BaseModel):
    profile_public: bool
