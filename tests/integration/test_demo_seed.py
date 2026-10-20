import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.challenge_types import ChallengeType
from app.domain.enums import ContentStatus, Origin, Role
from app.infra.db.models import Base, Challenge, Classroom, Mission, MissionChallenge, User
from app.infra.security import verify_password
from app.services.demo_service import DemoService
from app.services.exceptions import Conflict, ValidationFailed
from tests.integration.factories import make_user

PASSWORD = "senha-demo-123"


def row_counts(session: Session) -> dict[str, int]:
    return {
        table.name: session.scalar(select(func.count()).select_from(table))
        for table in Base.metadata.sorted_tables
    }


def test_T_SEED_01_one_published_challenge_per_type_in_the_demo_turma(session):
    created = DemoService(session).seed(lambda: PASSWORD)

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
    assert row_counts(session)["badges"] == 30


def test_T_SEED_01_seeding_twice_changes_nothing_and_asks_no_password(session):
    DemoService(session).seed(lambda: PASSWORD)
    before = row_counts(session)

    def no_password():
        raise AssertionError("the password is only needed to create prof_demo")

    assert DemoService(session).seed(no_password) == []
    assert row_counts(session) == before


def test_T_SEED_01_mismatched_passwords_create_nothing(session):
    with pytest.raises(ValidationFailed) as raised:
        DemoService(session).seed(lambda: None)

    assert raised.value.errors == ["As senhas não conferem."]
    assert session.scalar(select(User)) is None


def test_T_SEED_01_prof_demo_taken_by_a_student_aborts(session):
    make_user(session, "prof_demo")
    session.commit()

    with pytest.raises(Conflict) as raised:
        DemoService(session).seed(lambda: PASSWORD)

    assert raised.value.code == "demo_username_taken"
    assert row_counts(session)["classrooms"] == 0


def test_T_SEED_01_join_code_taken_by_another_professor_aborts(session):
    other = make_user(session, "prof_outro", Role.PROFESSOR)
    session.add(Classroom(name="Outra", join_code="DEMO01", professor_id=other.id))
    session.commit()

    with pytest.raises(Conflict) as raised:
        DemoService(session).seed(lambda: PASSWORD)

    assert raised.value.code == "demo_join_code_taken"
    assert row_counts(session)["missions"] == 0
    assert session.scalar(select(func.count()).select_from(User)) == 1


def test_T_SEED_01_password_follows_the_account_rules(session):
    with pytest.raises(ValidationFailed) as raised:
        DemoService(session).seed(lambda: "curta")

    assert raised.value.errors == ["A senha deve ter de 8 a 72 caracteres."]
    assert session.scalar(select(User)) is None
