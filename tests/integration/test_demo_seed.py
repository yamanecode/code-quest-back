from datetime import datetime, timedelta
from itertools import pairwise
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import TIMEZONE
from app.domain.challenge_types import ChallengeType
from app.domain.enums import ContentStatus, Origin, Role
from app.domain.gamification import week_start
from app.infra.db.models import (
    Base,
    Challenge,
    Classroom,
    ClassroomMember,
    Mission,
    MissionChallenge,
    Submission,
    User,
    UserBadge,
    XPEvent,
)
from app.infra.security import verify_password
from app.services.base_content_service import BaseContentService
from app.services.classroom_service import ClassroomService
from app.services.demo_service import DemoService
from app.services.exceptions import Conflict, ValidationFailed
from app.services.gamification_service import GamificationService
from tests.integration.factories import make_user

PASSWORD = "senha-demo-123"
STUDENT_PASSWORD = "senha-alunos-123"
STUDENTS = [f"demo_aluno{number}" for number in range(1, 7)]
BASE_DIR = Path(__file__).resolve().parents[2] / "content" / "base"


def row_counts(session: Session) -> dict[str, int]:
    return {
        table.name: session.scalar(select(func.count()).select_from(table))
        for table in Base.metadata.sorted_tables
    }


def test_T_SEED_01_one_published_challenge_per_type_in_the_demo_turma(session, clock, llm):
    created = DemoService(session, clock, llm).seed(lambda: PASSWORD)

    assert created == ["professor prof_demo", "turma Turma Demo (DEMO01)", "Missão de exemplo"]
    professor = session.scalar(select(User).where(User.username == "prof_demo"))
    assert professor.role == Role.PROFESSOR
    assert verify_password(PASSWORD, professor.password_hash)
    classroom = session.scalar(select(Classroom).where(Classroom.join_code == "DEMO01"))
    assert (classroom.name, classroom.professor_id) == ("Turma Demo", professor.id)
    mission = session.scalar(select(Mission))
    assert (mission.title, mission.classroom_id) == ("Missão de exemplo", classroom.id)
    assert mission.status == ContentStatus.PUBLISHED
    query = select(Challenge).join(MissionChallenge).order_by(MissionChallenge.position)
    challenges = list(session.scalars(query))
    assert [c.type for c in challenges] == list(ChallengeType)
    assert {c.status for c in challenges} == {ContentStatus.PUBLISHED}
    assert {c.origin for c in challenges} == {Origin.PROFESSOR}
    assert {c.owner_id for c in challenges} == {professor.id}
    assert row_counts(session)["badges"] == 26


def test_T_SEED_01_seeding_twice_changes_nothing_and_asks_no_password(session, clock, llm):
    DemoService(session, clock, llm).seed(lambda: PASSWORD)
    before = row_counts(session)

    def no_password():
        raise AssertionError("the password is only needed to create prof_demo")

    assert DemoService(session, clock, llm).seed(no_password) == []
    assert row_counts(session) == before


def test_T_SEED_01_mismatched_passwords_create_nothing(session, clock, llm):
    with pytest.raises(ValidationFailed) as raised:
        DemoService(session, clock, llm).seed(lambda: None)

    assert raised.value.errors == ["As senhas não conferem."]
    assert session.scalar(select(User)) is None


def test_T_SEED_01_prof_demo_taken_by_a_student_aborts(session, clock, llm):
    make_user(session, "prof_demo")
    session.commit()

    with pytest.raises(Conflict) as raised:
        DemoService(session, clock, llm).seed(lambda: PASSWORD)

    assert raised.value.code == "demo_username_taken"
    assert row_counts(session)["classrooms"] == 0


def test_T_SEED_01_join_code_taken_by_another_professor_aborts(session, clock, llm):
    other = make_user(session, "prof_outro", Role.PROFESSOR)
    session.add(Classroom(name="Outra", join_code="DEMO01", professor_id=other.id))
    session.commit()

    with pytest.raises(Conflict) as raised:
        DemoService(session, clock, llm).seed(lambda: PASSWORD)

    assert raised.value.code == "demo_join_code_taken"
    assert row_counts(session)["missions"] == 0
    assert session.scalar(select(func.count()).select_from(User)) == 1


def test_T_SEED_01_password_follows_the_account_rules(session, clock, llm):
    with pytest.raises(ValidationFailed) as raised:
        DemoService(session, clock, llm).seed(lambda: "curta")

    assert raised.value.errors == ["A senha deve ter de 8 a 72 caracteres."]
    assert session.scalar(select(User)) is None


@pytest.fixture
def base_game(session):
    BaseContentService(session).load(BASE_DIR)


def seed_with_students(session, clock, llm) -> list[str]:
    return DemoService(session, clock, llm).seed(lambda: PASSWORD, lambda: STUDENT_PASSWORD)


def user_id(session: Session, username: str) -> int:
    return session.scalar(select(User.id).where(User.username == username))


def test_T_SEED_02_six_students_join_the_demo_turma_with_varied_xp(session, clock, llm, base_game):
    created = seed_with_students(session, clock, llm)

    assert created[3:] == [f"estudante {name}" for name in STUDENTS]
    members = session.scalars(
        select(User.username)
        .join(ClassroomMember, ClassroomMember.user_id == User.id)
        .join(Classroom, Classroom.id == ClassroomMember.classroom_id)
        .where(Classroom.join_code == "DEMO01")
        .order_by(User.username)
    )
    assert list(members) == STUDENTS
    xp_query = (
        select(User.username, func.sum(XPEvent.amount))
        .join(XPEvent, XPEvent.user_id == User.id)
        .group_by(User.username)
    )
    assert dict(session.execute(xp_query).all()) == dict(
        zip(STUDENTS, [100, 70, 42, 27, 15, 2], strict=True)
    )
    assert set(session.scalars(select(XPEvent.amount))) == {10, 5, 2}
    wrong_query = (
        select(User.username, func.count())
        .join(Submission, Submission.user_id == User.id)
        .where(Submission.is_correct.is_(False))
        .group_by(User.username)
    )
    assert dict(session.execute(wrong_query).all()) == {
        "demo_aluno2": 2,
        "demo_aluno3": 6,
        "demo_aluno4": 4,
        "demo_aluno5": 2,
        "demo_aluno6": 3,
    }
    student = session.scalar(select(User).where(User.username == "demo_aluno1"))
    assert student.role == Role.STUDENT
    assert verify_password(STUDENT_PASSWORD, student.password_hash)


def assert_spread_from_week_start_to_now(session: Session, now: datetime) -> None:
    start = week_start(now)
    moments = sorted(session.scalars(select(Submission.created_at)))
    gaps = [later - earlier for earlier, later in pairwise([start, *moments])]
    assert moments[-1] == now
    assert min(gaps) > timedelta(0)
    assert max(gaps) - min(gaps) <= timedelta(microseconds=1)
    for model in (XPEvent, UserBadge):
        for moment in session.scalars(select(model.created_at)):
            assert start < moment <= now


def test_T_SEED_03_answers_are_spread_evenly_from_the_week_start_to_now(
    session, clock, llm, base_game
):
    seed_with_students(session, clock, llm)

    assert_spread_from_week_start_to_now(session, clock.now())


def test_T_SEED_03_a_window_of_five_minutes_still_holds_every_answer(
    session, clock, llm, base_game
):
    clock.set(datetime(2026, 10, 12, 0, 5, tzinfo=TIMEZONE))  # a Monday

    seed_with_students(session, clock, llm)

    assert_spread_from_week_start_to_now(session, clock.now())


def test_T_SEED_04_seeding_students_twice_changes_nothing_and_asks_no_password(
    session, clock, llm, base_game
):
    seed_with_students(session, clock, llm)
    before = row_counts(session)

    def no_password():
        raise AssertionError("passwords are only needed for missing accounts")

    assert DemoService(session, clock, llm).seed(no_password, no_password) == []
    assert row_counts(session) == before


def test_T_SEED_05_rankings_and_the_class_goal_show_the_students(session, clock, llm, base_game):
    seed_with_students(session, clock, llm)
    gamification = GamificationService(session, clock)

    ranking = gamification.ranking(user_id(session, "demo_aluno3"), "global", "week")
    classrooms = ClassroomService(session, clock, gamification)
    goal = classrooms.my_classrooms(user_id(session, "demo_aluno6"))[0].goal

    assert [(e.position, e.username, e.xp) for e in ranking.entries] == [
        (1, "demo_aluno1", 100),
        (2, "demo_aluno2", 70),
        (3, "demo_aluno3", 42),
        (4, "demo_aluno4", 27),
        (5, "demo_aluno5", 15),
    ]
    assert (goal.target, goal.progress, goal.completed) == (24, 17, False)


def test_T_SEED_06_wrong_answers_are_seeded_without_hints(session, clock, llm, base_game):
    seed_with_students(session, clock, llm)

    assert llm.prompts == []
    assert row_counts(session)["hint_events"] == 0


def test_T_SEED_07_no_students_without_the_option(session, clock, llm, base_game):
    DemoService(session, clock, llm).seed(lambda: PASSWORD)

    students = select(func.count()).select_from(User).where(User.role == Role.STUDENT)
    assert session.scalar(students) == 0


def test_T_SEED_07_students_need_the_base_game_and_nothing_is_created(session, clock, llm):
    def no_password():
        raise AssertionError("nothing is read before the base game check")

    with pytest.raises(Conflict) as raised:
        DemoService(session, clock, llm).seed(no_password, no_password)

    assert raised.value.code == "base_game_missing"
    assert raised.value.message == "Carregue o jogo base antes: load-base content/base"
    assert set(row_counts(session).values()) == {0}


def test_T_SEED_08_a_demo_student_name_owned_by_a_professor_aborts(session, clock, llm, base_game):
    make_user(session, "demo_aluno4", Role.PROFESSOR)
    session.commit()

    with pytest.raises(Conflict) as raised:
        seed_with_students(session, clock, llm)

    assert raised.value.code == "demo_username_taken"
    assert "demo_aluno4" in raised.value.message
    assert row_counts(session)["classrooms"] == 0


@pytest.mark.parametrize(
    ("password", "errors"),
    [(None, ["As senhas não conferem."]), ("curta", ["A senha deve ter de 8 a 72 caracteres."])],
)
def test_T_SEED_08_the_student_password_is_checked_before_anything_is_created(
    session, clock, llm, base_game, password, errors
):
    with pytest.raises(ValidationFailed) as raised:
        DemoService(session, clock, llm).seed(lambda: PASSWORD, lambda: password)

    assert raised.value.errors == errors
    assert row_counts(session)["classrooms"] == 0
