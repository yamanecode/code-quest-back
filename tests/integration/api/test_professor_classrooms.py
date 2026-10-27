import re

import pytest
from sqlalchemy import func, select

from app.api.deps import get_content_service
from app.domain.enums import Role
from app.infra.db.models import Classroom, XPEvent
from app.services.content_service import ContentService
from tests.integration.auth_helpers import bearer
from tests.integration.factories import (
    add_member,
    first_solve,
    make_challenge,
    make_classroom,
    make_user,
)

URL = "/api/professor/classrooms"


@pytest.fixture
def teacher(session):
    return make_user(session, "prof_ana", role=Role.PROFESSOR)


@pytest.fixture
def headers(teacher, clock):
    return bearer(teacher, clock)


def classroom_count(session):
    return session.scalar(select(func.count()).select_from(Classroom))


def test_T_PROF_01_create_classroom_returns_join_code(client, headers):
    response = client.post(URL, json={"name": "Turma 7B", "weekly_goal": 20}, headers=headers)

    assert response.status_code == 201
    body = response.json()
    assert re.fullmatch(r"[A-Z0-9]{6}", body["join_code"])
    assert body["name"] == "Turma 7B"
    assert body["weekly_goal"] == 20
    assert body["goal"] is None


def test_T_PROF_01_created_classroom_is_listed_back(client, headers):
    created = client.post(URL, json={"name": "Turma 7B"}, headers=headers).json()

    listed = client.get(URL, headers=headers).json()

    assert listed == [created]
    assert created["weekly_goal"] is None


def test_T_PROF_01_list_shows_only_own_classrooms(client, session, headers):
    make_classroom(session)
    client.post(URL, json={"name": "Minha"}, headers=headers)

    listed = client.get(URL, headers=headers).json()

    assert [item["name"] for item in listed] == ["Minha"]


def test_T_PROF_02_join_code_collision_is_retried(client, session, clock, headers):
    taken = make_classroom(session)
    codes = iter([taken.join_code, "NEW001"])
    client.app.dependency_overrides[get_content_service] = lambda: ContentService(
        session, clock, make_join_code=lambda: next(codes)
    )

    response = client.post(URL, json={"name": "Turma"}, headers=headers)

    assert response.status_code == 201
    assert response.json()["join_code"] == "NEW001"


def test_T_PROF_02_gives_up_after_repeated_collisions(session, clock, teacher):
    taken = make_classroom(session)
    service = ContentService(session, clock, make_join_code=lambda: taken.join_code)

    with pytest.raises(RuntimeError):
        service.create_classroom(teacher.id, "Turma", None)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"name": ""}, "O nome da turma deve ter de 1 a 60 caracteres."),
        ({"name": "a" * 61}, "O nome da turma deve ter de 1 a 60 caracteres."),
        ({"name": "Turma", "weekly_goal": 0}, "A meta semanal deve ser um número de 1 a 1000."),
        ({"name": "Turma", "weekly_goal": 1001}, "A meta semanal deve ser um número de 1 a 1000."),
    ],
)
def test_T_PROF_03_invalid_classroom_is_rejected(client, session, headers, body, message):
    response = client.post(URL, json=body, headers=headers)

    assert response.status_code == 422
    assert response.json()["detail"] == "validation_error"
    assert response.json()["errors"] == [message]
    assert classroom_count(session) == 0


def test_T_PROF_03_unknown_field_is_rejected(client, session, headers):
    response = client.post(URL, json={"name": "Turma", "join_code": "ABC123"}, headers=headers)

    assert response.status_code == 422
    assert classroom_count(session) == 0


def test_T_PROF_04_edit_name_and_weekly_goal(client, headers):
    created = client.post(URL, json={"name": "Antiga", "weekly_goal": 30}, headers=headers).json()

    response = client.put(
        f"{URL}/{created['id']}", json={"name": "Nova", "weekly_goal": None}, headers=headers
    )

    assert response.status_code == 200
    assert response.json() == {**created, "name": "Nova", "weekly_goal": None}
    fetched = client.get(f"{URL}/{created['id']}", headers=headers).json()
    assert fetched == response.json()
    assert fetched["goal"] is None


def test_T_PROF_04_edit_is_validated(client, headers):
    created = client.post(URL, json={"name": "Turma"}, headers=headers).json()

    response = client.put(
        f"{URL}/{created['id']}", json={"name": "Turma", "weekly_goal": 5000}, headers=headers
    )

    assert response.status_code == 422
    assert client.get(f"{URL}/{created['id']}", headers=headers).json()["weekly_goal"] is None


def close(client, headers, classroom_id):
    return client.post(f"{URL}/{classroom_id}/close", headers=headers)


def reopen(client, headers, classroom_id):
    return client.post(f"{URL}/{classroom_id}/reopen", headers=headers)


def test_T_PROF_CLOSE_01_close_and_reopen_toggle_the_flag(client, headers):
    created = client.post(URL, json={"name": "Turma 7B"}, headers=headers).json()
    assert created["closed"] is False

    closed = close(client, headers, created["id"])
    assert closed.status_code == 200
    assert closed.json() == {**created, "closed": True}
    assert client.get(f"{URL}/{created['id']}", headers=headers).json()["closed"] is True
    assert client.get(URL, headers=headers).json()[0]["closed"] is True

    reopened = reopen(client, headers, created["id"])
    assert reopened.status_code == 200
    assert reopened.json() == created


def test_T_PROF_CLOSE_02_closing_twice_changes_nothing(client, headers):
    created = client.post(URL, json={"name": "Turma 7B"}, headers=headers).json()

    first = close(client, headers, created["id"])
    second = close(client, headers, created["id"])

    assert second.status_code == 200
    assert second.json() == first.json()
    assert (
        reopen(client, headers, created["id"]).json()
        == reopen(client, headers, created["id"]).json()
    )


def test_T_PROF_CLOSE_03_editing_a_closed_turma_keeps_it_closed(client, headers):
    created = client.post(URL, json={"name": "Turma 7B"}, headers=headers).json()
    close(client, headers, created["id"])

    edited = client.put(
        f"{URL}/{created['id']}", json={"name": "Turma 7C", "weekly_goal": 8}, headers=headers
    )

    assert edited.status_code == 200
    assert edited.json()["closed"] is True
    assert edited.json()["name"] == "Turma 7C"


def test_T_PROF_CLOSE_04_only_the_owner_professor_can_close(client, session, clock, headers):
    other = make_classroom(session)
    student = bearer(make_user(session, "aluna"), clock)

    assert close(client, headers, other.id).status_code == 404
    assert reopen(client, headers, other.id).status_code == 404
    assert close(client, student, other.id).status_code == 403


def member_url(classroom_id, username):
    return f"{URL}/{classroom_id}/members/{username}"


def test_T_PROF_MEMBER_01_removing_a_student_ends_the_membership_and_keeps_the_history(
    client, session, clock, headers, teacher
):
    classroom = make_classroom(session, teacher)
    student = make_user(session, "aluna")
    add_member(session, student, classroom)
    first_solve(session, student, make_challenge(session))
    student_headers = bearer(student, clock)

    response = client.delete(member_url(classroom.id, "Aluna "), headers=headers)

    assert response.status_code == 204
    assert client.get("/api/classrooms", headers=student_headers).json() == []
    assert session.scalar(select(func.count()).select_from(XPEvent)) == 1
    assert client.get("/api/me", headers=student_headers).json()["xp"] == 10
    progress = client.get(f"{URL}/{classroom.id}/progress", headers=headers).json()
    assert progress["students"] == []


def test_T_PROF_MEMBER_02_unknown_or_foreign_targets_are_404(client, session, headers, teacher):
    classroom = make_classroom(session, teacher)
    outsider = make_user(session, "fora")
    add_member(session, make_user(session, "aluna"), make_classroom(session))
    other_turma = make_classroom(session)

    not_a_member = client.delete(member_url(classroom.id, outsider.username), headers=headers)
    no_such_user = client.delete(member_url(classroom.id, "ninguem"), headers=headers)
    foreign = client.delete(member_url(other_turma.id, "aluna"), headers=headers)

    assert not_a_member.status_code == no_such_user.status_code == 404
    assert not_a_member.json()["detail"] == no_such_user.json()["detail"] == "member_not_found"
    assert foreign.status_code == 404
    assert foreign.json()["detail"] == "classroom_not_found"


def test_T_PROF_MEMBER_03_students_cannot_remove_anyone(client, session, clock, teacher):
    classroom = make_classroom(session, teacher)
    student = make_user(session, "aluna")
    add_member(session, student, classroom)

    response = client.delete(member_url(classroom.id, "aluna"), headers=bearer(student, clock))

    assert response.status_code == 403


def test_T_PROF_MEMBER_04_a_removed_student_can_rejoin_with_the_same_code(
    client, session, clock, headers, teacher
):
    classroom = make_classroom(session, teacher)
    student = make_user(session, "aluna")
    add_member(session, student, classroom)
    client.delete(member_url(classroom.id, "aluna"), headers=headers)

    rejoin = client.post(
        "/api/classrooms/join",
        json={"join_code": classroom.join_code},
        headers=bearer(student, clock),
    )

    assert rejoin.status_code == 200


def new_code(client, headers, classroom_id):
    return client.post(f"{URL}/{classroom_id}/new-code", headers=headers)


def join(client, clock, student, code):
    return client.post(
        "/api/classrooms/join", json={"join_code": code}, headers=bearer(student, clock)
    )


def test_T_PROF_CODE_01_a_new_code_replaces_the_old_one_and_keeps_the_members(
    client, session, clock, headers, teacher
):
    classroom = make_classroom(session, teacher)
    member, leaked = make_user(session, "aluna"), make_user(session, "intruso")
    add_member(session, member, classroom)
    old_code = classroom.join_code

    response = new_code(client, headers, classroom.id)

    assert response.status_code == 200
    body = response.json()
    assert re.fullmatch(r"[A-Z0-9]{6}", body["join_code"])
    assert body["join_code"] != old_code
    assert client.get(f"{URL}/{classroom.id}", headers=headers).json() == body
    assert join(client, clock, leaked, old_code).status_code == 404
    assert join(client, clock, leaked, body["join_code"]).status_code == 200
    kept = client.get("/api/classrooms", headers=bearer(member, clock)).json()
    assert [item["id"] for item in kept] == [classroom.id]


def test_T_PROF_CODE_02_a_new_code_keeps_everything_else_of_the_turma(client, headers):
    created = client.post(URL, json={"name": "Turma 7B", "weekly_goal": 9}, headers=headers).json()
    close(client, headers, created["id"])

    renewed = new_code(client, headers, created["id"]).json()

    assert {**renewed, "join_code": None} == {**created, "closed": True, "join_code": None}


def test_T_PROF_CODE_03_only_the_owner_professor_can_renew_the_code(
    client, session, clock, headers
):
    other = make_classroom(session)
    student = bearer(make_user(session, "aluna"), clock)

    assert new_code(client, headers, other.id).status_code == 404
    assert new_code(client, student, other.id).status_code == 403
