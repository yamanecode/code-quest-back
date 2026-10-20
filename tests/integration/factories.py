"""Small builders that insert rows directly, so repository tests read like scenarios."""

from datetime import datetime
from itertools import count

from sqlalchemy.orm import Session

from app.core.clock import TIMEZONE
from app.domain.challenge_types import ChallengeType
from app.domain.enums import ContentStatus, HintSource, Origin, Role, XPReason
from app.infra.db.models import (
    Challenge,
    Classroom,
    ClassroomMember,
    HintEvent,
    Mission,
    MissionChallenge,
    Submission,
    User,
    XPEvent,
)

_sequence = count(1)

NOON = datetime(2026, 10, 14, 12, 0, tzinfo=TIMEZONE)  # a Wednesday

CONTENT = {
    ChallengeType.ORDERING: {
        "items": [
            {"id": "a", "text": "um"},
            {"id": "b", "text": "dois"},
            {"id": "c", "text": "três"},
        ],
        "solution": ["a", "b", "c"],
    },
    ChallengeType.GROUPING: {
        "groups": [{"id": "g1", "text": "Casa"}, {"id": "g2", "text": "Escola"}],
        "items": [
            {"id": "a", "text": "lavar"},
            {"id": "b", "text": "ler"},
            {"id": "c", "text": "varrer"},
            {"id": "d", "text": "estudar"},
        ],
        "solution": {"a": "g1", "b": "g2", "c": "g1", "d": "g2"},
    },
    ChallengeType.FILTERING: {
        "question": "Qual informação importa?",
        "items": [
            {"id": "a", "text": "preço"},
            {"id": "b", "text": "cor"},
            {"id": "c", "text": "peso"},
            {"id": "d", "text": "nome"},
        ],
        "solution": ["a"],
    },
    ChallengeType.PATTERN: {
        "sequence": ["2", "4", "8"],
        "options": [
            {"id": "a", "text": "16"},
            {"id": "b", "text": "10"},
            {"id": "c", "text": "12"},
            {"id": "d", "text": "14"},
        ],
        "solution": "a",
    },
}


CORRECT_ANSWER = {
    ChallengeType.ORDERING: {"order": ["a", "b", "c"]},
    ChallengeType.GROUPING: {"assignment": {"a": "g1", "b": "g2", "c": "g1", "d": "g2"}},
    ChallengeType.FILTERING: {"selected": ["a"]},
    ChallengeType.PATTERN: {"option": "a"},
}

WRONG_ANSWER = {
    ChallengeType.ORDERING: {"order": ["c", "b", "a"]},
    ChallengeType.GROUPING: {"assignment": {"a": "g1", "b": "g1", "c": "g1", "d": "g1"}},
    ChallengeType.FILTERING: {"selected": ["b"]},
    ChallengeType.PATTERN: {"option": "b"},
}


def _add(session: Session, row):
    session.add(row)
    session.flush()
    return row


def make_user(
    session: Session, username: str | None = None, role: Role = Role.STUDENT, public: bool = False
) -> User:
    name = username or f"user_{next(_sequence)}"
    return _add(session, User(username=name, password_hash="x", role=role, profile_public=public))


def make_classroom(
    session: Session, professor: User | None = None, weekly_goal: int | None = None
) -> Classroom:
    owner = professor or make_user(session, role=Role.PROFESSOR)
    code = f"C{next(_sequence):05d}"
    return _add(
        session,
        Classroom(name="Turma", join_code=code, professor_id=owner.id, weekly_goal=weekly_goal),
    )


def add_member(session: Session, user: User, classroom: Classroom) -> ClassroomMember:
    return _add(session, ClassroomMember(user_id=user.id, classroom_id=classroom.id))


def make_mission(
    session: Session,
    classroom: Classroom | None = None,
    status: ContentStatus = ContentStatus.PUBLISHED,
    title: str | None = None,
    position: int = 0,
) -> Mission:
    return _add(
        session,
        Mission(
            classroom_id=classroom.id if classroom else None,
            title=title or f"Missão {next(_sequence)}",
            position=position,
            status=status,
        ),
    )


def make_challenge(
    session: Session,
    owner: User | None = None,
    challenge_type: ChallengeType = ChallengeType.ORDERING,
    status: ContentStatus = ContentStatus.PUBLISHED,
    missions: tuple[Mission, ...] = (),
    explanation: str | None = None,
) -> Challenge:
    author = owner or make_user(session, role=Role.PROFESSOR)
    challenge = _add(
        session,
        Challenge(
            owner_id=author.id,
            title=f"Desafio {next(_sequence)}",
            statement="Enunciado de teste com tamanho suficiente.",
            type=challenge_type,
            content=CONTENT[challenge_type],
            explanation=explanation,
            status=status,
            origin=Origin.PROFESSOR,
        ),
    )
    for mission in missions:
        link(session, mission, challenge)
    return challenge


def link(session: Session, mission: Mission, challenge: Challenge, position: int = 0) -> None:
    _add(
        session,
        MissionChallenge(mission_id=mission.id, challenge_id=challenge.id, position=position),
    )


def submit(
    session: Session, user: User, challenge: Challenge, correct: bool, at: datetime = NOON
) -> Submission:
    return _add(
        session,
        Submission(
            user_id=user.id,
            challenge_id=challenge.id,
            answer={},
            is_correct=correct,
            created_at=at,
        ),
    )


def first_solve(
    session: Session, user: User, challenge: Challenge, amount: int = 10, at: datetime = NOON
) -> XPEvent:
    """A correct submission plus the XP event the service would grant for it."""
    submit(session, user, challenge, correct=True, at=at)
    return _add(
        session,
        XPEvent(
            user_id=user.id,
            challenge_id=challenge.id,
            amount=amount,
            reason=XPReason.FIRST_SOLVE,
            created_at=at,
        ),
    )


def hint(
    session: Session,
    user: User,
    challenge: Challenge,
    source: HintSource = HintSource.REQUEST,
    at: datetime = NOON,
    text: str = "Pense no começo.",
) -> HintEvent:
    return _add(
        session,
        HintEvent(
            user_id=user.id,
            challenge_id=challenge.id,
            source=source,
            level=1,
            text=text,
            discarded_count=0,
            created_at=at,
        ),
    )
