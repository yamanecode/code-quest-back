from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey,
    Enum, Text, func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, declarative_base
import enum

Base = declarative_base()


class UserRole(str, enum.Enum):
    student = "student"
    professor = "professor"


class ChallengeType(str, enum.Enum):
    steps = "steps"
    pattern = "pattern"
    algorithm = "algorithm"
    ordering = "ordering"
    abstraction = "abstraction"


class ChallengeCategory(str, enum.Enum):
    decomposition = "decomposition"
    pattern = "pattern"
    abstraction = "abstraction"
    algorithm = "algorithm"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.student, nullable=False)
    xp = Column(Integer, default=0, nullable=False)
    level = Column(Integer, default=1, nullable=False)
    streak = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    submissions = relationship("Submission", back_populates="user")
    xp_events = relationship("XPEvent", back_populates="user")
    user_badges = relationship("UserBadge", back_populates="user")


class Challenge(Base):
    __tablename__ = "challenges"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    difficulty = Column(Integer, default=1)  # 1=easy, 2=medium, 3=hard
    category = Column(Enum(ChallengeCategory), nullable=False)
    type = Column(Enum(ChallengeType), nullable=False)
    content = Column(JSONB, nullable=False)  # shape varies by type
    is_daily = Column(Boolean, default=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    submissions = relationship("Submission", back_populates="challenge")
    mission_challenges = relationship("MissionChallenge", back_populates="challenge")


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    answer = Column(JSONB, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    xp_earned = Column(Integer, default=0)
    attempt_number = Column(Integer, default=1)
    ai_feedback = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="submissions")
    challenge = relationship("Challenge", back_populates="submissions")


class Badge(Base):
    __tablename__ = "badges"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    icon = Column(String, nullable=False)  # emoji or icon key
    trigger_condition = Column(String, nullable=False)  # e.g. "10_day_streak"

    user_badges = relationship("UserBadge", back_populates="badge")


class UserBadge(Base):
    __tablename__ = "user_badges"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    badge_id = Column(Integer, ForeignKey("badges.id"), primary_key=True)
    earned_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="user_badges")
    badge = relationship("Badge", back_populates="user_badges")


class Mission(Base):
    __tablename__ = "missions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    xp_reward = Column(Integer, default=0)
    is_sequential = Column(Boolean, default=False)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)

    mission_challenges = relationship("MissionChallenge", back_populates="mission")


class MissionChallenge(Base):
    __tablename__ = "mission_challenges"

    mission_id = Column(Integer, ForeignKey("missions.id"), primary_key=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), primary_key=True)
    order = Column(Integer, default=0)

    mission = relationship("Mission", back_populates="mission_challenges")
    challenge = relationship("Challenge", back_populates="mission_challenges")


class XPEvent(Base):
    __tablename__ = "xp_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    reason = Column(String, nullable=False)  # e.g. "challenge_correct", "streak_bonus"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="xp_events")