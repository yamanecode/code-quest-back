from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.domain.challenge_types import SKILL_LABELS, to_student_view
from app.domain.gamification import daily_pick, xp_for_wrong_attempts
from app.domain.grading import InvalidAnswer, grade
from app.infra.db.models import Challenge, Mission
from app.infra.repositories.challenges import ChallengeRepository
from app.infra.repositories.classrooms import ClassroomRepository
from app.infra.repositories.daily import DailyRepository
from app.infra.repositories.missions import MissionRepository
from app.infra.repositories.submissions import SubmissionRepository
from app.infra.repositories.xp import XPRepository
from app.services.exceptions import NotFound, ValidationFailed
from app.services.gamification_service import BadgeInfo, GamificationService


@dataclass(frozen=True)
class MissionSummary:
    id: int
    title: str
    description: str | None
    total: int
    solved: int


@dataclass(frozen=True)
class ClassroomMissions:
    id: int
    name: str
    missions: list[MissionSummary]


@dataclass(frozen=True)
class MissionList:
    base: list[MissionSummary]
    classrooms: list[ClassroomMissions]


@dataclass(frozen=True)
class ChallengeSummary:
    id: int
    title: str
    type: str
    skill: str
    solved: bool


@dataclass(frozen=True)
class MissionDetail:
    id: int
    title: str
    description: str | None
    challenges: list[ChallengeSummary]


@dataclass(frozen=True)
class StudentChallenge:
    """A challenge as the student sees it: no solution, no explanation."""

    id: int
    title: str
    statement: str
    type: str
    skill: str
    content: dict
    solved: bool


@dataclass(frozen=True)
class SubmissionResult:
    is_correct: bool
    xp_earned: int
    xp: int
    level: int
    title: str
    level_up: bool
    new_badges: list[BadgeInfo]
    explanation: str | None
    hint: str | None


@dataclass(frozen=True)
class DailyChallenge:
    challenge: ChallengeSummary | None
    all_solved: bool


def _summary(challenge: Challenge, solved_ids: set[int]) -> ChallengeSummary:
    return ChallengeSummary(
        challenge.id,
        challenge.title,
        challenge.type,
        SKILL_LABELS[challenge.type],
        challenge.id in solved_ids,
    )


class PlayService:
    """What a student does: browse visible missions, open challenges, answer, daily challenge."""

    def __init__(self, session: Session, clock: Clock, gamification: GamificationService) -> None:
        self.session = session
        self.clock = clock
        self.gamification = gamification
        self.missions = MissionRepository(session)
        self.challenges = ChallengeRepository(session)
        self.classrooms = ClassroomRepository(session)
        self.submissions = SubmissionRepository(session)
        self.xp = XPRepository(session)
        self.daily = DailyRepository(session)

    def list_missions(self, user_id: int) -> MissionList:
        visible = self.missions.visible_missions(user_id)
        by_mission = self.missions.published_challenge_ids_by_mission(m.id for m in visible)
        solved = self.submissions.solved_challenge_ids(user_id)

        def summary(mission: Mission) -> MissionSummary:
            ids = by_mission[mission.id]
            done = len(solved.intersection(ids))
            return MissionSummary(mission.id, mission.title, mission.description, len(ids), done)

        base = [summary(m) for m in visible if m.classroom_id is None]
        classrooms = [
            ClassroomMissions(
                classroom.id,
                classroom.name,
                [summary(m) for m in visible if m.classroom_id == classroom.id],
            )
            for classroom in self.classrooms.member_classrooms(user_id)
        ]
        return MissionList(base, classrooms)

    def get_mission(self, user_id: int, mission_id: int) -> MissionDetail:
        if mission_id not in self.missions.visible_mission_ids(user_id):
            raise NotFound("mission_not_found", "Missão não encontrada.")
        mission = self.missions.get(mission_id)
        solved = self.submissions.solved_challenge_ids(user_id)
        challenges = self.missions.published_challenges(mission_id)
        return MissionDetail(
            mission.id,
            mission.title,
            mission.description,
            [_summary(challenge, solved) for challenge in challenges],
        )

    def get_challenge(self, user_id: int, challenge_id: int) -> StudentChallenge:
        challenge = self._visible_challenge(user_id, challenge_id)
        view = to_student_view(challenge.type, challenge.content, seed=f"{challenge.id}:{user_id}")
        return StudentChallenge(
            id=challenge.id,
            title=challenge.title,
            statement=challenge.statement,
            type=view["type"],
            skill=view["skill"],
            content=view["content"],
            solved=challenge.id in self.submissions.solved_challenge_ids(user_id),
        )

    def submit(self, user_id: int, challenge_id: int, answer: dict) -> SubmissionResult:
        challenge = self._visible_challenge(user_id, challenge_id)
        try:
            is_correct = grade(challenge.type, challenge.content, answer)
        except InvalidAnswer as error:
            raise ValidationFailed("invalid_answer", "Resposta em formato inválido.") from error
        already_solved = challenge_id in self.submissions.solved_challenge_ids(user_id)
        first_solve = is_correct and not already_solved
        before = self.gamification.level_info(user_id)
        now = self.clock.now()

        self.submissions.add(user_id, challenge_id, answer, is_correct, now)
        xp_earned = 0
        if first_solve:
            wrong = self.submissions.wrong_attempts_before_first_solve(user_id, challenge_id)
            xp_earned = xp_for_wrong_attempts(wrong)
            self.xp.add(user_id, challenge_id, xp_earned, now)
        new_badges = self.gamification.award_new_badges(user_id) if is_correct else []
        explanation = challenge.explanation if is_correct else None
        self.session.commit()

        after = self.gamification.level_info(user_id)
        return SubmissionResult(
            is_correct=is_correct,
            xp_earned=xp_earned,
            xp=after.xp,
            level=after.level,
            title=after.title,
            level_up=after.level > before.level,
            new_badges=new_badges,
            explanation=explanation,
            hint=None,
        )

    def daily_challenge(self, user_id: int) -> DailyChallenge:
        today = self.clock.today()
        assignment = self.daily.daily_assignment(user_id, today)
        if assignment is None:
            visible = self.missions.visible_published_challenge_ids(user_id)
            candidates = visible - self.submissions.solved_before(user_id, today)
            challenge_id = daily_pick(user_id, today, candidates)
            if challenge_id is None:
                return DailyChallenge(challenge=None, all_solved=True)
            assignment = self.daily.add(user_id, today, challenge_id, self.clock.now())
            self.session.commit()
        challenge = self.challenges.get(assignment.challenge_id)
        solved = self.submissions.solved_challenge_ids(user_id)
        return DailyChallenge(challenge=_summary(challenge, solved), all_solved=False)

    def _visible_challenge(self, user_id: int, challenge_id: int) -> Challenge:
        # Drafts, challenges of other turmas and missing ids all look the same.
        if challenge_id not in self.missions.visible_published_challenge_ids(user_id):
            raise NotFound("challenge_not_found", "Desafio não encontrado.")
        return self.challenges.get(challenge_id)
