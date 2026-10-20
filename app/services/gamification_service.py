from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.domain.badges import BADGES, Badge, BadgeStats, badge_codes_earned, badge_display
from app.domain.challenge_types import ChallengeType
from app.domain.enums import ContentStatus, Role
from app.domain.gamification import (
    RankedRow,
    RankingPeriod,
    RankingScope,
    RankRow,
    completed_every_mission,
    completion_pct,
    dense_rank,
    level_for,
    mission_completed,
    period_start,
    streak,
    title_for,
    window_around,
    xp_to_next_level,
)
from app.infra.db.models import Classroom
from app.infra.repositories.badges import BadgeRepository
from app.infra.repositories.classrooms import ClassroomRepository
from app.infra.repositories.daily import DailyRepository
from app.infra.repositories.hints import HintRepository
from app.infra.repositories.missions import MissionRepository
from app.infra.repositories.submissions import SubmissionRepository
from app.infra.repositories.users import UserRepository
from app.infra.repositories.xp import UserXP, XPRepository
from app.services.exceptions import NotFound, ValidationFailed


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


@dataclass(frozen=True)
class RankingEntry:
    position: int
    username: str
    xp: int
    is_me: bool
    profile_public: bool


@dataclass(frozen=True)
class Ranking:
    scope: str
    period: str
    entries: list[RankingEntry]


@dataclass(frozen=True)
class PublicBadge:
    code: str
    name: str
    tier: str
    emoji: str


@dataclass(frozen=True)
class PublicProfile:
    username: str
    level: int
    title: str
    badges: list[PublicBadge]


@dataclass(frozen=True)
class StudentProgress:
    username: str
    xp_in_class: int
    level: int
    solved_in_class: int
    missions_completed_in_class: int
    hints_used: int
    streak: int


@dataclass(frozen=True)
class ClassroomProgress:
    completed_all_pct: int
    students: list[StudentProgress]


def _ranking_entries(
    rows: list[UserXP], ranked: list[RankedRow], me_id: int | None
) -> list[RankingEntry]:
    public = {row.user_id: row.profile_public for row in rows}
    return [
        RankingEntry(row.position, row.username, row.xp, row.user_id == me_id, public[row.user_id])
        for row in ranked
    ]


def _ranked(rows: list[UserXP]) -> list[RankedRow]:
    return dense_rank(RankRow(row.user_id, row.username, row.xp) for row in rows)


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

    def public_profile(self, username: str) -> PublicProfile:
        user = self.users.get_by_username(username.lower())
        # Professors, the system account and private profiles all look like a missing player.
        if user is None or user.role != Role.STUDENT or not user.profile_public:
            raise NotFound("player_not_found", "Perfil não encontrado.")
        progress = self.level_info(user.id)
        earned = self.badges.earned(user.id)
        badges = [
            PublicBadge(badge.code, badge.name, badge.tier, badge.emoji)
            for badge in BADGES
            if badge.code in earned
        ]
        return PublicProfile(user.username, progress.level, progress.title, badges)

    # Rankings

    def ranking(
        self, user_id: int, scope: str, period: str, classroom_id: int | None = None
    ) -> Ranking:
        """The student's position with up to two neighbours above and below."""
        since = period_start(RankingPeriod(period), self.clock.now())
        if RankingScope(scope) == RankingScope.CLASSROOM:
            if classroom_id is None:
                raise ValidationFailed("classroom_required", "Escolha uma turma.")
            if self.classrooms.get_membership(user_id, classroom_id) is None:
                raise NotFound("classroom_not_found", "Turma não encontrada.")
            rows = self.xp.xp_in_classroom_since(classroom_id, since)
        else:
            rows = self.xp.xp_by_user_since(since)
        nearby = window_around(_ranked(rows), user_id)
        return Ranking(scope, period, _ranking_entries(rows, nearby, me_id=user_id))

    def classroom_ranking(self, professor_id: int, classroom_id: int, period: str) -> Ranking:
        """Full turma ranking for the professor who owns the turma."""
        self._own_classroom(professor_id, classroom_id)
        since = period_start(RankingPeriod(period), self.clock.now())
        rows = self.xp.xp_in_classroom_since(classroom_id, since)
        entries = _ranking_entries(rows, _ranked(rows), me_id=None)
        return Ranking(RankingScope.CLASSROOM, period, entries)

    # Professor progress table

    def classroom_progress(self, professor_id: int, classroom_id: int) -> ClassroomProgress:
        self._own_classroom(professor_id, classroom_id)
        xp_in_class = {row.user_id: row.xp for row in self.xp.xp_in_classroom_total(classroom_id)}
        published = [
            mission.id
            for mission in self.missions.list_for_classroom(classroom_id)
            if mission.status == ContentStatus.PUBLISHED
        ]
        by_mission = self.missions.published_challenge_ids_by_mission(published)
        missions = [ids for ids in by_mission.values() if ids]
        class_challenges = self.classrooms.goal_challenge_ids(classroom_id)

        students = []
        completed_all = 0
        for member in self.classrooms.members(classroom_id):
            solved = self.submissions.solved_challenge_ids(member.id)
            completed_all += completed_every_mission(missions, solved)
            students.append(
                StudentProgress(
                    username=member.username,
                    xp_in_class=xp_in_class.get(member.id, 0),
                    level=level_for(self.xp.xp_total(member.id)),
                    solved_in_class=len(solved & class_challenges),
                    missions_completed_in_class=self._completed_count(missions, solved),
                    hints_used=self.hints.requested_count(member.id, class_challenges),
                    streak=streak(self.submissions.solve_days(member.id), self.clock.today()),
                )
            )
        return ClassroomProgress(completion_pct(completed_all, len(students)), students)

    @staticmethod
    def _completed_count(missions: list[list[int]], solved: set[int]) -> int:
        return sum(mission_completed(ids, solved) for ids in missions)

    def _own_classroom(self, professor_id: int, classroom_id: int) -> Classroom:
        classroom = self.classrooms.get(classroom_id)
        if classroom is None or classroom.professor_id != professor_id:
            raise NotFound("classroom_not_found", "Turma não encontrada.")
        return classroom

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
