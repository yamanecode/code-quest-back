from collections.abc import Iterable
from datetime import date, datetime

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.domain.enums import ContentStatus
from app.infra.db.models import (
    Challenge,
    ClassGoalReward,
    Classroom,
    ClassroomMember,
    Mission,
    MissionChallenge,
    User,
    XPEvent,
)

PUBLISHED = ContentStatus.PUBLISHED


class ClassroomRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self, name: str, join_code: str, professor_id: int, weekly_goal: int | None = None
    ) -> Classroom:
        classroom = Classroom(
            name=name, join_code=join_code, professor_id=professor_id, weekly_goal=weekly_goal
        )
        self.session.add(classroom)
        self.session.flush()
        return classroom

    def get(self, classroom_id: int) -> Classroom | None:
        return self.session.get(Classroom, classroom_id)

    def get_by_join_code(self, join_code: str) -> Classroom | None:
        return self.session.scalar(select(Classroom).where(Classroom.join_code == join_code))

    def list_by_professor(self, professor_id: int) -> list[Classroom]:
        query = select(Classroom).where(Classroom.professor_id == professor_id)
        return list(self.session.scalars(query.order_by(Classroom.id)))

    # Membership

    def add_member(self, user_id: int, classroom_id: int) -> ClassroomMember:
        membership = ClassroomMember(user_id=user_id, classroom_id=classroom_id)
        self.session.add(membership)
        self.session.flush()
        return membership

    def get_membership(self, user_id: int, classroom_id: int) -> ClassroomMember | None:
        query = select(ClassroomMember).where(
            ClassroomMember.user_id == user_id, ClassroomMember.classroom_id == classroom_id
        )
        return self.session.scalar(query)

    def remove_member(self, membership: ClassroomMember) -> None:
        self.session.delete(membership)
        self.session.flush()

    def member_classrooms(self, user_id: int) -> list[Classroom]:
        query = (
            select(Classroom)
            .join(ClassroomMember, ClassroomMember.classroom_id == Classroom.id)
            .where(ClassroomMember.user_id == user_id)
            .order_by(Classroom.id)
        )
        return list(self.session.scalars(query))

    def members(self, classroom_id: int) -> list[User]:
        query = (
            select(User)
            .join(ClassroomMember, ClassroomMember.user_id == User.id)
            .where(ClassroomMember.classroom_id == classroom_id)
            .order_by(User.username)
        )
        return list(self.session.scalars(query))

    def member_count(self, classroom_id: int) -> int:
        query = select(func.count()).where(ClassroomMember.classroom_id == classroom_id)
        return self.session.scalar(query) or 0

    # Class goal (spec §5.3): first solves of current members on the turma's
    # published challenges inside published missions.

    def _members(self, classroom_id: int):
        return select(ClassroomMember.user_id).where(ClassroomMember.classroom_id == classroom_id)

    def _goal_challenges(self, classroom_id: int):
        return (
            select(MissionChallenge.challenge_id)
            .join(Mission, Mission.id == MissionChallenge.mission_id)
            .join(Challenge, Challenge.id == MissionChallenge.challenge_id)
            .where(
                Mission.classroom_id == classroom_id,
                Mission.status == PUBLISHED,
                Challenge.status == PUBLISHED,
            )
        )

    def _goal_solves(self, classroom_id: int):
        return (
            XPEvent.user_id.in_(self._members(classroom_id)),
            XPEvent.challenge_id.in_(self._goal_challenges(classroom_id)),
        )

    def goal_challenge_ids(self, classroom_id: int) -> set[int]:
        return set(self.session.scalars(self._goal_challenges(classroom_id)))

    def goal_classrooms(self, user_id: int, challenge_id: int) -> list[Classroom]:
        """The student's turmas in which this challenge counts toward the class goal."""
        turmas_with_challenge = (
            select(Mission.classroom_id)
            .join(MissionChallenge, MissionChallenge.mission_id == Mission.id)
            .join(Challenge, Challenge.id == MissionChallenge.challenge_id)
            .where(
                MissionChallenge.challenge_id == challenge_id,
                Mission.status == PUBLISHED,
                Challenge.status == PUBLISHED,
            )
        )
        query = (
            select(Classroom)
            .join(ClassroomMember, ClassroomMember.classroom_id == Classroom.id)
            .where(ClassroomMember.user_id == user_id, Classroom.id.in_(turmas_with_challenge))
            .order_by(Classroom.id)
        )
        return list(self.session.scalars(query))

    def goal_progress(self, classroom_id: int, week_start: datetime) -> int:
        query = select(func.count()).where(
            *self._goal_solves(classroom_id), XPEvent.created_at >= week_start
        )
        return self.session.scalar(query) or 0

    def goal_available(self, classroom_id: int, week_start: datetime) -> int:
        """Open first solves: members x goal challenges - first solves made before the week."""
        challenges = self.session.scalar(
            select(func.count()).select_from(
                self._goal_challenges(classroom_id).distinct().subquery()
            )
        )
        solved_before = self.session.scalar(
            select(func.count()).where(
                *self._goal_solves(classroom_id), XPEvent.created_at < week_start
            )
        )
        return self.member_count(classroom_id) * challenges - solved_before

    def goal_contributors(self, classroom_id: int, week_start: datetime) -> set[int]:
        query = select(XPEvent.user_id).where(
            *self._goal_solves(classroom_id), XPEvent.created_at >= week_start
        )
        return set(self.session.scalars(query))

    def has_goal_rewards(self, classroom_id: int, week_start: date) -> bool:
        condition = exists().where(
            ClassGoalReward.classroom_id == classroom_id, ClassGoalReward.week_start == week_start
        )
        return bool(self.session.scalar(select(condition)))

    def add_goal_rewards(
        self, classroom_id: int, week_start: date, user_ids: Iterable[int], created_at: datetime
    ) -> None:
        for user_id in user_ids:
            reward = ClassGoalReward(
                user_id=user_id,
                classroom_id=classroom_id,
                week_start=week_start,
                created_at=created_at,
            )
            self.session.add(reward)
        self.session.flush()

    def goals_contributed(self, user_id: int) -> int:
        query = select(func.count()).where(ClassGoalReward.user_id == user_id)
        return self.session.scalar(query) or 0
