from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.badges import Tier
from app.domain.challenge_types import ChallengeType
from app.domain.enums import ContentStatus, HintSource, Origin, Role
from app.infra.db.base import Base


def _enum(enum_class: type[StrEnum], name: str) -> Enum:
    # Store the lower-case values ("student"), not the member names ("STUDENT").
    return Enum(enum_class, name=name, values_callable=lambda members: [m.value for m in members])


class _Row(Base):
    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _user_fk(ondelete: str | None = None) -> Mapped[int]:
    return mapped_column(ForeignKey("users.id", ondelete=ondelete))


def _challenge_fk(ondelete: str | None = None) -> Mapped[int]:
    return mapped_column(ForeignKey("challenges.id", ondelete=ondelete))


class User(_Row):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(30), unique=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[Role] = mapped_column(_enum(Role, "user_role"))
    profile_public: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    recovery_code_hash: Mapped[str | None] = mapped_column(String(64))
    recovery_code_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recovery_code_confirmed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )


class Classroom(_Row):
    __tablename__ = "classrooms"
    __table_args__ = (CheckConstraint("weekly_goal BETWEEN 1 AND 1000", name="weekly_goal_range"),)

    name: Mapped[str] = mapped_column(String(60))
    join_code: Mapped[str] = mapped_column(String(6), unique=True)
    professor_id: Mapped[int] = _user_fk()
    weekly_goal: Mapped[int | None] = mapped_column(Integer)
    closed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class ClassroomMember(_Row):
    __tablename__ = "classroom_members"
    __table_args__ = (UniqueConstraint("user_id", "classroom_id"),)

    user_id: Mapped[int] = _user_fk("CASCADE")
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id", ondelete="CASCADE"))


class Mission(_Row):
    __tablename__ = "missions"

    classroom_id: Mapped[int | None] = mapped_column(ForeignKey("classrooms.id"))
    title: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(String(400))
    position: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[ContentStatus] = mapped_column(
        _enum(ContentStatus, "content_status"), default=ContentStatus.DRAFT
    )


class Challenge(_Row):
    __tablename__ = "challenges"

    owner_id: Mapped[int] = _user_fk()
    title: Mapped[str] = mapped_column(String(80))
    statement: Mapped[str] = mapped_column(Text)
    type: Mapped[ChallengeType] = mapped_column(_enum(ChallengeType, "challenge_type"))
    content: Mapped[dict] = mapped_column(JSON)
    explanation: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ContentStatus] = mapped_column(
        _enum(ContentStatus, "content_status"), default=ContentStatus.DRAFT
    )
    origin: Mapped[Origin] = mapped_column(_enum(Origin, "challenge_origin"))


class MissionChallenge(_Row):
    __tablename__ = "mission_challenges"
    __table_args__ = (UniqueConstraint("mission_id", "challenge_id"),)

    mission_id: Mapped[int] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"))
    challenge_id: Mapped[int] = _challenge_fk("CASCADE")
    position: Mapped[int] = mapped_column(Integer)


class Submission(_Row):
    __tablename__ = "submissions"
    __table_args__ = (Index("ix_submissions_user_id_challenge_id", "user_id", "challenge_id"),)

    user_id: Mapped[int] = _user_fk()
    challenge_id: Mapped[int] = _challenge_fk()
    answer: Mapped[dict] = mapped_column(JSON)
    is_correct: Mapped[bool] = mapped_column(Boolean)


class XPEvent(_Row):
    __tablename__ = "xp_events"
    __table_args__ = (UniqueConstraint("user_id", "challenge_id", "reason"),)

    user_id: Mapped[int] = _user_fk()
    challenge_id: Mapped[int] = _challenge_fk()
    amount: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(30))


class HintEvent(_Row):
    __tablename__ = "hint_events"

    user_id: Mapped[int] = _user_fk()
    challenge_id: Mapped[int] = _challenge_fk("CASCADE")
    source: Mapped[HintSource] = mapped_column(_enum(HintSource, "hint_source"))
    level: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    discarded_count: Mapped[int] = mapped_column(Integer, default=0)


class DailyAssignment(_Row):
    __tablename__ = "daily_assignments"
    __table_args__ = (UniqueConstraint("user_id", "day"),)

    user_id: Mapped[int] = _user_fk()
    day: Mapped[date] = mapped_column(Date)
    challenge_id: Mapped[int] = _challenge_fk("CASCADE")


class ClassGoalReward(_Row):
    __tablename__ = "class_goal_rewards"
    __table_args__ = (UniqueConstraint("user_id", "classroom_id", "week_start"),)

    user_id: Mapped[int] = _user_fk()
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id"))
    week_start: Mapped[date] = mapped_column(Date)


class Badge(_Row):
    __tablename__ = "badges"

    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(String(200))
    tier: Mapped[Tier] = mapped_column(_enum(Tier, "badge_tier"))
    emoji: Mapped[str] = mapped_column(String(16))
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)


class UserBadge(_Row):
    __tablename__ = "user_badges"
    __table_args__ = (UniqueConstraint("user_id", "badge_id"),)

    user_id: Mapped[int] = _user_fk()
    badge_id: Mapped[int] = mapped_column(ForeignKey("badges.id"))
