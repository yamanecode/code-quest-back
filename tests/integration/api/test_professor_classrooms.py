import re

import pytest
from sqlalchemy import func, select

from app.api.deps import get_content_service
from app.domain.enums import Role
from app.infra.db.models import Classroom
from app.services.content_service import ContentService
from tests.integration.auth_helpers import bearer
from tests.integration.factories import make_classroom, make_user

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
