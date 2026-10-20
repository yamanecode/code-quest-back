from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.domain.badges import BADGES, Badge, BadgeStats, badge_codes_earned, badge_display
from app.domain.challenge_types import ChallengeType
from app.domain.gamification import (
    level_for,
    mission_completed,
    streak,
    title_for,
    xp_to_next_level,
)
from app.infra.repositories.badges import BadgeRepository
from app.infra.repositories.classrooms import ClassroomRepository
from app.infra.repositories.daily import DailyRepository
from app.infra.repositories.hints import HintRepository
from app.infra.repositories.missions import MissionRepository
from app.infra.repositories.submissions import SubmissionRepository
from app.infra.repositories.users import UserRepository
from app.infra.repositories.xp import XPRepository


@dataclass(frozen=True)
class BadgeInfo:
    code: str
    name: str
    description: str
    tier: str
    emoji: str


@dataclass(frozen=True)
class ProfileBadge:
    code: str
    name: str
    description: str
    tier: str
    emoji: str
    hidden: bool
    earned: bool
    earned_at: datetime | None


@dataclass(frozen=True)
class LevelInfo:
    xp: int
    level: int
    title: str


@dataclass(frozen=True)
class Profile:
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
    badges: list[ProfileBadge]


class GamificationService:
    """A student's progress: XP, level, streak, completed missions and badges."""

    def __init__(self, session: Session, clock: Clock) -> None:
        self.session = session
        self.clock = clock
        self.users = UserRepository(session)
        self.xp = XPRepository(session)
        self.submissions = SubmissionRepository(session)
        self.missions = MissionRepository(session)
        self.hints = HintRepository(session)
        self.daily = DailyRepository(session)
        self.classrooms = ClassroomRepository(session)
        self.badges = BadgeRepository(session)

    def level_info(self, user_id: int) -> LevelInfo:
        xp = self.xp.xp_total(user_id)
        level = level_for(xp)
        return LevelInfo(xp, level, title_for(level))

    def award_new_badges(self, user_id: int) -> list[BadgeInfo]:
        """Awards every badge whose condition became true; the caller commits."""
        new_codes = badge_codes_earned(self._stats(user_id)) - set(self.badges.earned(user_id))
        if new_codes:
            self.badges.award(user_id, new_codes, self.clock.now())
        return [
            BadgeInfo(badge.code, badge.name, badge.description, badge.tier, badge.emoji)
            for badge in BADGES
            if badge.code in new_codes
        ]

    def profile(self, user_id: int) -> Profile:
        user = self.users.get(user_id)
        stats = self._stats(user_id)
        progress = self.level_info(user_id)
        earned = self.badges.earned(user_id)
        return Profile(
            username=user.username,
            role=user.role,
            xp=progress.xp,
            level=progress.level,
            title=progress.title,
            xp_to_next_level=xp_to_next_level(progress.xp),
            streak=stats.streak,
            missions_completed=stats.missions_completed,
            solved_by_skill={t: stats.solved_by_type.get(t, 0) for t in ChallengeType},
            first_try_solves=stats.first_try_solves,
            profile_public=user.profile_public,
            badges=[self._profile_badge(badge, earned.get(badge.code)) for badge in BADGES],
        )

    def set_profile_public(self, user_id: int, profile_public: bool) -> bool:
        user = self.users.get(user_id)
        user.profile_public = profile_public
        self.session.commit()
        return user.profile_public

    @staticmethod
    def _profile_badge(badge: Badge, earned_at: datetime | None) -> ProfileBadge:
        name, description = badge_display(badge, earned=earned_at is not None)
        return ProfileBadge(
            code=badge.code,
            name=name,
            description=description,
            tier=badge.tier,
            emoji=badge.emoji,
            hidden=badge.hidden,
            earned=earned_at is not None,
            earned_at=earned_at,
        )

    def _completed_missions(self, user_id: int) -> tuple[int, int]:
        """Completed visible missions, and how many of them had no requested hint."""
        solved = self.submissions.solved_challenge_ids(user_id)
        hinted = self.hints.requested_challenge_ids(user_id)
        visible = self.missions.visible_mission_ids(user_id)
        by_mission = self.missions.published_challenge_ids_by_mission(visible)
        completed = [ids for ids in by_mission.values() if mission_completed(ids, solved)]
        without_hints = [ids for ids in completed if hinted.isdisjoint(ids)]
        return len(completed), len(without_hints)

    def _stats(self, user_id: int) -> BadgeStats:
        today = self.clock.today()
        by_type = self.xp.first_solves_by_type(user_id)
        completed, completed_without_hints = self._completed_missions(user_id)
        return BadgeStats(
            solved_total=sum(by_type.values()),
            solved_by_type=by_type,
            missions_completed=completed,
            missions_completed_without_hints=completed_without_hints,
            streak=streak(self.submissions.solve_days(user_id), today),
            level=level_for(self.xp.xp_total(user_id)),
            first_try_solves=self.xp.first_try_solves(user_id),
            dailies_solved=self.daily.dailies_solved(user_id),
            goals_contributed=self.classrooms.goals_contributed(user_id),
            types_first_solved_today=frozenset(self.xp.first_solve_types_on(user_id, today)),
        )
