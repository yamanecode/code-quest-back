import copy
import secrets
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.domain.challenge_types import (
    SKILL_LABELS,
    ChallengeDraft,
    ChallengeType,
    challenge_errors,
    structure_changed,
)
from app.domain.content import (
    JOIN_CODE_ALPHABET,
    JOIN_CODE_LENGTH,
    classroom_errors,
    copy_title,
    mission_errors,
)
from app.domain.enums import ContentStatus, Origin
from app.infra.db.models import Challenge, Classroom, Mission
from app.infra.repositories.challenges import ChallengeRepository
from app.infra.repositories.classrooms import ClassroomRepository
from app.infra.repositories.missions import MissionRepository
from app.services.classroom_service import Goal, class_goal
from app.services.exceptions import Conflict, NotFound, ValidationFailed

JOIN_CODE_ATTEMPTS = 10


def random_join_code() -> str:
    return "".join(secrets.choice(JOIN_CODE_ALPHABET) for _ in range(JOIN_CODE_LENGTH))


@dataclass(frozen=True)
class ClassroomView:
    id: int
    name: str
    join_code: str
    weekly_goal: int | None
    closed: bool
    goal: Goal | None


@dataclass(frozen=True)
class ChallengeRef:
    id: int
    title: str
    type: str
    status: str


@dataclass(frozen=True)
class MissionView:
    id: int
    classroom_id: int
    title: str
    description: str | None
    position: int
    status: str
    challenges: list[ChallengeRef]


@dataclass(frozen=True)
class SolveStatsView:
    attempted: int
    solved: int


@dataclass(frozen=True)
class ChallengeView:
    id: int
    title: str
    statement: str
    type: str
    skill: str
    content: dict
    explanation: str | None
    status: str
    origin: str
    locked: bool
    solve_stats: SolveStatsView


def draft_of(challenge: Challenge) -> ChallengeDraft:
    return ChallengeDraft(
        challenge.title,
        challenge.statement,
        challenge.type,
        challenge.content,
        challenge.explanation,
    )


@dataclass(frozen=True)
class MissionDraft:
    title: str
    description: str | None
    position: int
    challenges: list[ChallengeDraft]


def add_published_mission(
    session: Session,
    owner_id: int,
    draft: MissionDraft,
    origin: Origin,
    classroom_id: int | None = None,
) -> None:
    """Store a mission and its challenges, all published, in the given order (seed and base)."""
    missions = MissionRepository(session)
    challenges = ChallengeRepository(session)
    mission = missions.add(
        title=draft.title,
        position=draft.position,
        classroom_id=classroom_id,
        description=draft.description,
        status=ContentStatus.PUBLISHED,
    )
    rows = [
        challenges.add(
            owner_id=owner_id,
            title=challenge.title,
            statement=challenge.statement,
            challenge_type=ChallengeType(challenge.type),
            content=challenge.content,
            explanation=challenge.explanation,
            origin=origin,
            status=ContentStatus.PUBLISHED,
        )
        for challenge in draft.challenges
    ]
    missions.set_challenges(mission.id, [row.id for row in rows])


def _challenge_not_found() -> NotFound:
    return NotFound("challenge_not_found", "Desafio não encontrado.")


def _check(errors: list[str]) -> None:
    if errors:
        raise ValidationFailed(errors=errors)


class ContentService:
    """Professor authoring: turmas, missions and challenges, always scoped to their owner."""

    def __init__(
        self,
        session: Session,
        clock: Clock,
        make_join_code: Callable[[], str] = random_join_code,
    ) -> None:
        self.session = session
        self.clock = clock
        self.make_join_code = make_join_code
        self.classrooms = ClassroomRepository(session)
        self.missions = MissionRepository(session)
        self.challenges = ChallengeRepository(session)

    # Turmas

    def list_classrooms(self, professor_id: int) -> list[ClassroomView]:
        return [self._classroom_view(c) for c in self.classrooms.list_by_professor(professor_id)]

    def create_classroom(
        self, professor_id: int, name: str, weekly_goal: int | None
    ) -> ClassroomView:
        _check(classroom_errors(name, weekly_goal))
        classroom = self.classrooms.add(
            name.strip(), self._free_join_code(), professor_id, weekly_goal
        )
        self.session.commit()
        return self._classroom_view(classroom)

    def get_classroom(self, professor_id: int, classroom_id: int) -> ClassroomView:
        return self._classroom_view(self._own_classroom(professor_id, classroom_id))

    def update_classroom(
        self, professor_id: int, classroom_id: int, name: str, weekly_goal: int | None
    ) -> ClassroomView:
        classroom = self._own_classroom(professor_id, classroom_id)
        _check(classroom_errors(name, weekly_goal))
        classroom.name = name.strip()
        classroom.weekly_goal = weekly_goal
        self.session.commit()
        return self._classroom_view(classroom)

    def renew_join_code(self, professor_id: int, classroom_id: int) -> ClassroomView:
        """Replace a leaked code: the old one stops working, members stay."""
        classroom = self._own_classroom(professor_id, classroom_id)
        classroom.join_code = self._free_join_code()
        self.session.commit()
        return self._classroom_view(classroom)

    def remove_member(self, professor_id: int, classroom_id: int, username: str) -> None:
        self._own_classroom(professor_id, classroom_id)
        membership = self.classrooms.get_membership_by_username(
            classroom_id, username.strip().lower()
        )
        if membership is None:
            raise NotFound("member_not_found", "Estudante não encontrado nesta turma.")
        # Same as the student leaving: only the membership goes away.
        self.classrooms.remove_member(membership)
        self.session.commit()

    def close_classroom(self, professor_id: int, classroom_id: int) -> ClassroomView:
        return self._set_closed(professor_id, classroom_id, True)

    def reopen_classroom(self, professor_id: int, classroom_id: int) -> ClassroomView:
        return self._set_closed(professor_id, classroom_id, False)

    def _set_closed(self, professor_id: int, classroom_id: int, closed: bool) -> ClassroomView:
        classroom = self._own_classroom(professor_id, classroom_id)
        classroom.closed = closed
        self.session.commit()
        return self._classroom_view(classroom)

    def _classroom_view(self, classroom: Classroom) -> ClassroomView:
        return ClassroomView(
            classroom.id,
            classroom.name,
            classroom.join_code,
            classroom.weekly_goal,
            classroom.closed,
            class_goal(self.classrooms, classroom, self.clock.now()),
        )

    # Missions

    def list_missions(self, professor_id: int, classroom_id: int) -> list[MissionView]:
        self._own_classroom(professor_id, classroom_id)
        return [self._mission_view(m) for m in self.missions.list_for_classroom(classroom_id)]

    def create_mission(
        self,
        professor_id: int,
        classroom_id: int,
        title: str,
        description: str | None,
        position: int | None,
    ) -> MissionView:
        self._own_classroom(professor_id, classroom_id)
        _check(mission_errors(title, description))
        if position is None:
            position = len(self.missions.list_for_classroom(classroom_id))
        mission = self.missions.add(title.strip(), position, classroom_id, description)
        self.session.commit()
        return self._mission_view(mission)

    def set_mission_order(
        self, professor_id: int, classroom_id: int, mission_ids: list[int]
    ) -> list[MissionView]:
        """Renumber every mission of the turma 0..n-1 in the given order, all or nothing."""
        self._own_classroom(professor_id, classroom_id)
        missions = {m.id: m for m in self.missions.list_for_classroom(classroom_id)}
        if len(set(mission_ids)) != len(mission_ids) or set(mission_ids) != set(missions):
            raise ValidationFailed(
                errors=["Informe todas as missões da turma, cada uma uma única vez."]
            )
        for position, mission_id in enumerate(mission_ids):
            missions[mission_id].position = position
        self.session.commit()
        return [self._mission_view(missions[mission_id]) for mission_id in mission_ids]

    def get_mission(self, professor_id: int, mission_id: int) -> MissionView:
        return self._mission_view(self._own_mission(professor_id, mission_id))

    def update_mission(
        self,
        professor_id: int,
        mission_id: int,
        title: str,
        description: str | None,
        position: int,
    ) -> MissionView:
        mission = self._own_mission(professor_id, mission_id)
        _check(mission_errors(title, description))
        mission.title = title.strip()
        mission.description = description
        mission.position = position
        self.session.commit()
        return self._mission_view(mission)

    def delete_mission(self, professor_id: int, mission_id: int) -> None:
        mission = self._own_mission(professor_id, mission_id)
        if self.missions.has_submissions(mission_id):
            raise Conflict(
                "mission_has_submissions", "Esta missão já tem respostas e não pode ser excluída."
            )
        self.missions.delete(mission)
        self.session.commit()

    def set_mission_challenges(
        self, professor_id: int, mission_id: int, challenge_ids: list[int]
    ) -> MissionView:
        mission = self._own_mission(professor_id, mission_id)
        if len(set(challenge_ids)) != len(challenge_ids):
            raise ValidationFailed(errors=["Cada desafio só pode aparecer uma vez na missão."])
        if self.challenges.owned_ids(professor_id, challenge_ids) != set(challenge_ids):
            raise _challenge_not_found()
        self.missions.set_challenges(mission_id, challenge_ids)
        self.session.commit()
        return self._mission_view(mission)

    def publish_mission(self, professor_id: int, mission_id: int) -> MissionView:
        mission = self._own_mission(professor_id, mission_id)
        if not self.missions.has_published_challenge(mission_id):
            raise Conflict("mission_empty", "A missão precisa de pelo menos um desafio publicado.")
        return self._set_mission_status(mission, ContentStatus.PUBLISHED)

    def unpublish_mission(self, professor_id: int, mission_id: int) -> MissionView:
        mission = self._own_mission(professor_id, mission_id)
        return self._set_mission_status(mission, ContentStatus.DRAFT)

    def _set_mission_status(self, mission: Mission, status: ContentStatus) -> MissionView:
        mission.status = status
        self.session.commit()
        return self._mission_view(mission)

    def _mission_view(self, mission: Mission) -> MissionView:
        challenges = [self.challenges.get(i) for i in self.missions.challenge_ids(mission.id)]
        return MissionView(
            id=mission.id,
            classroom_id=mission.classroom_id,
            title=mission.title,
            description=mission.description,
            position=mission.position,
            status=mission.status,
            challenges=[ChallengeRef(c.id, c.title, c.type, c.status) for c in challenges],
        )

    # Challenges

    def list_challenges(self, professor_id: int) -> list[ChallengeView]:
        return [self._challenge_view(c) for c in self.challenges.list_by_owner(professor_id)]

    def create_challenge(
        self,
        professor_id: int,
        draft: ChallengeDraft,
        origin: Origin = Origin.PROFESSOR,
        mission_id: int | None = None,
    ) -> ChallengeView:
        """Save a new draft challenge; with `mission_id` it is also added at the mission's end."""
        _check(challenge_errors(draft))
        if mission_id is not None:
            self._own_mission(professor_id, mission_id)
        challenge = self.challenges.add(
            owner_id=professor_id,
            title=draft.title,
            statement=draft.statement,
            challenge_type=ChallengeType(draft.type),
            content=draft.content,
            explanation=draft.explanation,
            origin=origin,
        )
        if mission_id is not None:
            ids = self.missions.challenge_ids(mission_id)
            self.missions.set_challenges(mission_id, [*ids, challenge.id])
        self.session.commit()
        return self._challenge_view(challenge)

    def get_challenge(self, professor_id: int, challenge_id: int) -> ChallengeView:
        return self._challenge_view(self._own_challenge(professor_id, challenge_id))

    def get_draft(self, professor_id: int, challenge_id: int) -> ChallengeDraft:
        """Only the challenge's own data, for the AI review."""
        return draft_of(self._own_challenge(professor_id, challenge_id))

    def update_challenge(
        self, professor_id: int, challenge_id: int, draft: ChallengeDraft
    ) -> ChallengeView:
        challenge = self._own_challenge(professor_id, challenge_id)
        # Rules first: structure_changed expects well-formed content.
        _check(challenge_errors(draft))
        if self.challenges.has_submissions(challenge_id) and (
            draft.type != challenge.type
            or structure_changed(draft.type, challenge.content, draft.content)
        ):
            raise Conflict(
                "challenge_locked",
                "Este desafio já tem respostas. Altere só os textos ou duplique o desafio.",
            )
        challenge.title = draft.title
        challenge.statement = draft.statement
        challenge.type = ChallengeType(draft.type)
        challenge.content = draft.content
        challenge.explanation = draft.explanation
        self.session.commit()
        return self._challenge_view(challenge)

    def delete_challenge(self, professor_id: int, challenge_id: int) -> None:
        challenge = self._own_challenge(professor_id, challenge_id)
        if self.challenges.has_submissions(challenge_id):
            raise Conflict(
                "challenge_has_submissions",
                "Este desafio já tem respostas e não pode ser excluído.",
            )
        self.challenges.delete(challenge)
        self.session.commit()

    def duplicate_challenge(self, professor_id: int, challenge_id: int) -> ChallengeView:
        original = self._own_challenge(professor_id, challenge_id)
        challenge = self.challenges.add(
            owner_id=professor_id,
            title=copy_title(original.title),
            statement=original.statement,
            challenge_type=original.type,
            content=copy.deepcopy(original.content),
            explanation=original.explanation,
            origin=Origin.PROFESSOR,
        )
        self.session.commit()
        return self._challenge_view(challenge)

    def publish_challenge(self, professor_id: int, challenge_id: int) -> ChallengeView:
        challenge = self._own_challenge(professor_id, challenge_id)
        _check(challenge_errors(draft_of(challenge)))
        return self._set_challenge_status(challenge, ContentStatus.PUBLISHED)

    def unpublish_challenge(self, professor_id: int, challenge_id: int) -> ChallengeView:
        challenge = self._own_challenge(professor_id, challenge_id)
        return self._set_challenge_status(challenge, ContentStatus.DRAFT)

    def _set_challenge_status(self, challenge: Challenge, status: ContentStatus) -> ChallengeView:
        challenge.status = status
        self.session.commit()
        return self._challenge_view(challenge)

    def _challenge_view(self, challenge: Challenge) -> ChallengeView:
        stats = self.challenges.solve_stats(challenge.id)
        return ChallengeView(
            id=challenge.id,
            title=challenge.title,
            statement=challenge.statement,
            type=challenge.type,
            skill=SKILL_LABELS[challenge.type],
            content=challenge.content,
            explanation=challenge.explanation,
            status=challenge.status,
            origin=challenge.origin,
            locked=stats.attempted > 0,
            solve_stats=SolveStatsView(stats.attempted, stats.solved),
        )

    def _own_challenge(self, professor_id: int, challenge_id: int) -> Challenge:
        challenge = self.challenges.get(challenge_id)
        if challenge is None or challenge.owner_id != professor_id:
            raise _challenge_not_found()
        return challenge

    def _free_join_code(self) -> str:
        for _ in range(JOIN_CODE_ATTEMPTS):
            code = self.make_join_code()
            if self.classrooms.get_by_join_code(code) is None:
                return code
        # 36^6 codes exist; reaching this means the generator is broken, not bad luck.
        raise RuntimeError("could not generate a free join code")

    def _own_classroom(self, professor_id: int, classroom_id: int) -> Classroom:
        classroom = self.classrooms.get(classroom_id)
        # Another professor's turma looks exactly like a missing one.
        if classroom is None or classroom.professor_id != professor_id:
            raise NotFound("classroom_not_found", "Turma não encontrada.")
        return classroom

    def _own_mission(self, professor_id: int, mission_id: int) -> Mission:
        mission = self.missions.get(mission_id)
        # Base missions (no turma) belong to the system account, never to a professor.
        if mission is None or mission.classroom_id is None:
            raise NotFound("mission_not_found", "Missão não encontrada.")
        classroom = self.classrooms.get(mission.classroom_id)
        if classroom.professor_id != professor_id:
            raise NotFound("mission_not_found", "Missão não encontrada.")
        return mission
