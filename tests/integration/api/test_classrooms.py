import pytest
from sqlalchemy import func, select

from app.domain.enums import Role
from app.infra.db.models import ClassroomMember, Submission, XPEvent
from tests.integration.auth_helpers import bearer
from tests.integration.factories import (
    add_member,
    first_solve,
    make_challenge,
    make_classroom,
    make_mission,
    make_user,
)


@pytest.fixture
def student(session):
    return make_user(session, "aluna", role=Role.STUDENT)


@pytest.fixture
def headers(student, clock):
    return bearer(student, clock)


def join(client, headers, code):
    return client.post("/api/classrooms/join", json={"join_code": code}, headers=headers)


def memberships(session, student):
    query = select(func.count()).where(ClassroomMember.user_id == student.id)
    return session.scalar(query)


def test_T_CLASS_01_join_with_valid_code(client, session, headers):
    classroom = make_classroom(session)

    response = join(client, headers, classroom.join_code)

    assert response.status_code == 200
    assert response.json() == {"id": classroom.id, "name": classroom.name}
    listed = client.get("/api/classrooms", headers=headers).json()
    assert listed == [{"id": classroom.id, "name": classroom.name, "goal": None}]


def test_T_CLASS_01_code_is_case_and_space_insensitive(client, session, headers):
    classroom = make_classroom(session)

    response = join(client, headers, f"  {classroom.join_code.lower()} ")

    assert response.status_code == 200


def test_T_CLASS_02_invalid_code_is_404(client, session, headers, student):
    response = join(client, headers, "NOPE99")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "invalid_join_code",
        "message": "Código de turma inválido.",
    }
    assert memberships(session, student) == 0


def test_T_CLASS_03_joining_twice_is_idempotent(client, session, headers, student):
    classroom = make_classroom(session)

    first = join(client, headers, classroom.join_code)
    second = join(client, headers, classroom.join_code)

    assert second.status_code == 200
    assert second.json() == first.json()
    assert memberships(session, student) == 1


def test_T_CLASS_04_student_can_be_in_two_classrooms(client, session, headers):
    first, second = make_classroom(session), make_classroom(session)
    join(client, headers, first.join_code)
    join(client, headers, second.join_code)

    listed = client.get("/api/classrooms", headers=headers).json()

    assert [item["id"] for item in listed] == [first.id, second.id]


def test_T_CLASS_04_list_shows_only_my_classrooms(client, session, headers):
    mine, other = make_classroom(session), make_classroom(session)
    add_member(session, make_user(session), other)
    join(client, headers, mine.join_code)

    listed = client.get("/api/classrooms", headers=headers).json()

    assert [item["id"] for item in listed] == [mine.id]


def test_T_CLASS_05_leave_removes_membership_and_keeps_history(client, session, headers, student):
    classroom = make_classroom(session)
    add_member(session, student, classroom)
    mission = make_mission(session, classroom)
    first_solve(session, student, make_challenge(session, missions=(mission,)))

    response = client.delete(f"/api/classrooms/{classroom.id}/membership", headers=headers)

    assert response.status_code == 204
    assert client.get("/api/classrooms", headers=headers).json() == []
    assert memberships(session, student) == 0
    assert session.scalar(select(func.count()).select_from(XPEvent)) == 1
    assert session.scalar(select(func.count()).select_from(Submission)) == 1


def test_T_CLASS_06_leaving_a_classroom_you_are_not_in_is_404(client, session, headers):
    classroom = make_classroom(session)
    add_member(session, make_user(session), classroom)

    response = client.delete(f"/api/classrooms/{classroom.id}/membership", headers=headers)
    missing = client.delete("/api/classrooms/9999/membership", headers=headers)

    assert response.status_code == 404
    assert missing.status_code == 404
    assert session.scalar(select(func.count()).select_from(ClassroomMember)) == 1
