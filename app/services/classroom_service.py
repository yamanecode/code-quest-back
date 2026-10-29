from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.domain.gamification import goal_reached, goal_target, week_start
from app.infra.db.models import Classroom
from app.infra.repositories.classrooms import ClassroomRepository
from app.services.exceptions import NotFound
from app.services.gamification_service import GamificationService


@dataclass(frozen=True)
class ClassroomRef:
    id: int
    name: str


@dataclass(frozen=True)
class Goal:
    target: int
    progress: int
    week_start: date
    completed: bool


@dataclass(frozen=True)
class MyClassroom:
    id: int
    name: str
    closed: bool
    goal: Goal | None


def class_goal(classrooms: ClassroomRepository, classroom: Classroom, now: datetime) -> Goal | None:
    """This week's class goal (RF-19); None when closed or nothing is left to solve."""
    if classroom.closed:
        return None
    start = week_start(now)
    target = goal_target(
        classroom.weekly_goal,
        classrooms.member_count(classroom.id),
        classrooms.goal_available(classroom.id, start),
    )
    if target is None:
        return None
    progress = classrooms.goal_progress(classroom.id, start)
    return Goal(target, progress, start.date(), goal_reached(progress, target))


class ClassroomService:
    """A student's turmas: join, leave and the weekly class goal."""

    def __init__(self, session: Session, clock: Clock, gamification: GamificationService) -> None:
        self.session = session
        self.clock = clock
        self.gamification = gamification
        self.classrooms = ClassroomRepository(session)

    def join(self, user_id: int, join_code: str) -> ClassroomRef:
        classroom = self.classrooms.get_by_join_code(join_code.strip().upper())
        # A closed turma answers like a wrong code, so its code reveals nothing.
        if classroom is None or classroom.closed:
            raise NotFound("invalid_join_code", "Código de turma inválido.")
        if self.classrooms.get_membership(user_id, classroom.id) is None:
            self.classrooms.add_member(user_id, classroom.id)
            self.session.commit()
        return ClassroomRef(classroom.id, classroom.name)

    def leave(self, user_id: int, classroom_id: int) -> None:
        membership = self.classrooms.get_membership(user_id, classroom_id)
        if membership is None:
            raise NotFound("classroom_not_found", "Turma não encontrada.")
        # Only the membership goes away; XP, badges and submissions belong to the student.
        self.classrooms.remove_member(membership)
        self.session.commit()

    def my_classrooms(self, user_id: int) -> list[MyClassroom]:
        now = self.clock.now()
        return [
            MyClassroom(
                classroom.id,
                classroom.name,
                classroom.closed,
                class_goal(self.classrooms, classroom, now),
            )
            for classroom in self.classrooms.member_classrooms(user_id)
        ]

    def reward_completed_goals(self, user_id: int, challenge_id: int) -> None:
        """Rewards the contributors of every goal this solve completed; the caller commits.

        The submitter's badges are left to the caller so they come back in the response.
        """
        now = self.clock.now()
        for classroom in self.classrooms.goal_classrooms(user_id, challenge_id):
            goal = class_goal(self.classrooms, classroom, now)
            if goal is None or not goal.completed:
                continue
            if self.classrooms.has_goal_rewards(classroom.id, goal.week_start):
                continue
            contributors = self.classrooms.goal_contributors(classroom.id, week_start(now))
            self.classrooms.add_goal_rewards(classroom.id, goal.week_start, contributors, now)
            for member_id in sorted(contributors - {user_id}):
                self.gamification.award_new_badges(member_id)
