import hashlib
import hmac
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import get_settings
from app.domain.challenge_types import SKILL_LABELS, to_student_view
from app.domain.enums import Origin
from app.domain.gamification import level_for, title_for, xp_for_wrong_attempts
from app.domain.grading import InvalidAnswer, answer_from_student, grade
from app.domain.novelty import MissionCandidate, is_new, next_challenge
from app.infra.db.models import Challenge, Mission
from app.infra.repositories.challenges import ChallengeRepository
from app.infra.repositories.classrooms import ClassroomRepository
from app.infra.repositories.missions import MissionRepository
from app.infra.repositories.submissions import SubmissionRepository
from app.infra.repositories.xp import XPRepository
from app.services.ai_service import AIService
from app.services.classroom_service import ClassroomService
from app.services.exceptions import Conflict, NotFound, ValidationFailed
from app.services.gamification_service import BadgeInfo, GamificationService


@dataclass(frozen=True)
class MissionSummary:
    id: int
    title: str
    description: str | None
    total: int
    solved: int
    is_new: bool
    has_new_challenges: bool


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
    is_new: bool


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
    is_new: bool
    explanation: str | None
    cooldown_seconds_left: int


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
class NextChallenge:
    """What the Continuar card opens."""

    mission_id: int
    mission_title: str
    challenge_id: int
    challenge_title: str
    is_new: bool


def view_seed(challenge_id: int, user_id: int) -> str:
    """Seed of a student's view of a challenge; keyed by a server secret so it can't be redone."""
    key = get_settings().JWT_SECRET.encode()
    message = f"student-view:{challenge_id}:{user_id}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _already_solved() -> Conflict:
    return Conflict("already_solved", "Você já resolveu este desafio.")


def _challenge_is_new(challenge: Challenge, answered: set[int], now: datetime) -> bool:
    return is_new(
        challenge.published_at,
        now,
        is_base=challenge.origin == Origin.BASE,
        answered=challenge.id in answered,
    )


def _mission_is_new(mission: Mission, started: bool, now: datetime) -> bool:
    return is_new(mission.published_at, now, is_base=mission.classroom_id is None, answered=started)


def _candidates(
    missions: Iterable[Mission], by_mission: dict[int, list[int]]
) -> list[MissionCandidate]:
    return [
        MissionCandidate(
            id=mission.id,
            is_base=mission.classroom_id is None,
            published_at=mission.published_at,
            position=mission.position,
            challenge_ids=tuple(by_mission[mission.id]),
        )
        for mission in missions
    ]


def _summary(
    challenge: Challenge, solved_ids: set[int], answered: set[int], now: datetime
) -> ChallengeSummary:
    return ChallengeSummary(
        challenge.id,
        challenge.title,
        challenge.type,
        SKILL_LABELS[challenge.type],
        challenge.id in solved_ids,
        _challenge_is_new(challenge, answered, now),
    )


class PlayService:
    """What a student does: browse visible missions, open challenges, answer, continue."""

    def __init__(
        self,
        session: Session,
        clock: Clock,
        gamification: GamificationService,
        goals: ClassroomService,
        ai: AIService,
    ) -> None:
        self.session = session
        self.clock = clock
        self.gamification = gamification
        self.goals = goals
        self.ai = ai
        self.missions = MissionRepository(session)
        self.challenges = ChallengeRepository(session)
        self.classrooms = ClassroomRepository(session)
        self.submissions = SubmissionRepository(session)
        self.xp = XPRepository(session)

    def list_missions(self, user_id: int) -> MissionList:
        visible = self.missions.visible_missions(user_id)
        by_mission = self.missions.published_challenge_ids_by_mission(m.id for m in visible)
        solved = self.submissions.solved_challenge_ids(user_id)
        answered = self.submissions.answered_challenge_ids(user_id)
        challenges = self.challenges.get_many(cid for ids in by_mission.values() for cid in ids)
        now = self.clock.now()

        def summary(mission: Mission) -> MissionSummary:
            ids = by_mission[mission.id]
            started = not answered.isdisjoint(ids)
            new_inside = any(_challenge_is_new(challenges[i], answered, now) for i in ids)
            return MissionSummary(
                id=mission.id,
                title=mission.title,
                description=mission.description,
                total=len(ids),
                solved=len(solved.intersection(ids)),
                is_new=_mission_is_new(mission, started, now),
                has_new_challenges=started and new_inside,
            )

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
        answered = self.submissions.answered_challenge_ids(user_id)
        challenges = self.missions.published_challenges(mission_id)
        now = self.clock.now()
        return MissionDetail(
            mission.id,
            mission.title,
            mission.description,
            [_summary(challenge, solved, answered, now) for challenge in challenges],
        )

    def get_challenge(self, user_id: int, challenge_id: int) -> StudentChallenge:
        challenge = self._visible_challenge(user_id, challenge_id)
        view = to_student_view(challenge.type, challenge.content, view_seed(challenge.id, user_id))
        solved = self.submissions.has_solved(user_id, challenge_id)
        answered = self.submissions.answered_challenge_ids(user_id)
        return StudentChallenge(
            id=challenge.id,
            title=challenge.title,
            statement=challenge.statement,
            type=view["type"],
            skill=view["skill"],
            content=view["content"],
            solved=solved,
            is_new=_challenge_is_new(challenge, answered, self.clock.now()),
            # Shown again once solved, so a closed challenge can still be reviewed.
            explanation=challenge.explanation if solved else None,
            cooldown_seconds_left=self.ai.cooldown_seconds_left(user_id, challenge_id),
        )

    def submit(self, user_id: int, challenge_id: int, answer: dict) -> SubmissionResult:
        challenge = self._visible_challenge(user_id, challenge_id)
        if self.submissions.has_solved(user_id, challenge_id):
            raise _already_solved()
        seed = view_seed(challenge.id, user_id)
        try:
            # From here on the answer uses stored ids: storage, grading and the hint prompt.
            answer = answer_from_student(challenge.type, challenge.content, seed, answer)
            is_correct = grade(challenge.type, challenge.content, answer)
        except InvalidAnswer as error:
            raise ValidationFailed("invalid_answer", "Resposta em formato inválido.") from error
        before = self.gamification.level_info(user_id)
        now = self.clock.now()

        self.submissions.add(user_id, challenge_id, answer, is_correct, now)
        xp_earned = 0
        new_badges = []
        hint = None
        if is_correct:
            wrong = self.submissions.wrong_attempts(user_id, challenge_id)
            xp_earned = xp_for_wrong_attempts(wrong)
            self.xp.add(user_id, challenge_id, xp_earned, now)
            # Goal rewards first, so a class_goal badge is among the submitter's new badges.
            self.goals.reward_completed_goals(user_id, challenge_id)
            new_badges = self.gamification.award_new_badges(user_id)
        else:
            hint = self.ai.hint_after_wrong(user_id, challenge, answer)
        self.session.commit()

        xp = before.xp + xp_earned
        level = level_for(xp)
        return SubmissionResult(
            is_correct=is_correct,
            xp_earned=xp_earned,
            xp=xp,
            level=level,
            title=title_for(level),
            level_up=level > before.level,
            new_badges=new_badges,
            explanation=challenge.explanation if is_correct else None,
            hint=hint,
        )

    def continue_for(self, user_id: int) -> NextChallenge | None:
        """The challenge of the Continuar card; None when every visible challenge is solved."""
        visible = self.missions.visible_missions(user_id)
        by_mission = self.missions.published_challenge_ids_by_mission(m.id for m in visible)
        picked = next_challenge(
            _candidates(visible, by_mission),
            solved=self.submissions.solved_challenge_ids(user_id),
            last_challenge_id=self.submissions.last_answered_challenge_id(user_id),
        )
        if picked is None:
            return None
        mission_id, challenge_id = picked
        mission = next(m for m in visible if m.id == mission_id)
        challenge = self.challenges.get(challenge_id)
        answered = self.submissions.answered_challenge_ids(user_id)
        return NextChallenge(
            mission_id=mission.id,
            mission_title=mission.title,
            challenge_id=challenge.id,
            challenge_title=challenge.title,
            is_new=_challenge_is_new(challenge, answered, self.clock.now()),
        )

    def _visible_challenge(self, user_id: int, challenge_id: int) -> Challenge:
        # Drafts, challenges of other turmas and missing ids all look the same.
        if challenge_id not in self.missions.visible_published_challenge_ids(user_id):
            raise NotFound("challenge_not_found", "Desafio não encontrado.")
        return self.challenges.get(challenge_id)
