import pytest

from app.api.deps import require_professor
from app.api.routers import professor
from app.domain.enums import Role
from app.infra.security import create_token
from tests.integration.auth_helpers import bearer
from tests.integration.factories import (
    CORRECT_ANSWER,
    make_challenge,
    make_classroom,
    make_mission,
    make_user,
)

PROFESSOR_ROUTE = "/api/professor/classrooms"


def test_T_ACL_01_professor_router_requires_professor_role():
    guards = [dependency.dependency for dependency in professor.router.dependencies]

    assert require_professor in guards


def test_T_ACL_01_student_gets_403_on_professor_routes(client, session, clock):
    student = make_user(session, role=Role.STUDENT)

    response = client.get(PROFESSOR_ROUTE, headers=bearer(student, clock))

    assert response.status_code == 403
    assert response.json()["detail"] == "forbidden"


def test_T_ACL_01_professor_passes_the_professor_guard(client, session, clock):
    teacher = make_user(session, role=Role.PROFESSOR)

    response = client.get(PROFESSOR_ROUTE, headers=bearer(teacher, clock))

    assert response.status_code == 200


def test_T_ACL_01_professor_route_without_token_is_401(client):
    assert client.get(PROFESSOR_ROUTE).status_code == 401


def test_T_ACL_01_professor_gets_403_on_student_routes(client, session, clock):
    teacher = make_user(session, role=Role.PROFESSOR)

    response = client.get("/api/classrooms", headers=bearer(teacher, clock))

    assert response.status_code == 403


def test_T_ACL_01_token_of_system_account_is_rejected(client, session, clock):
    system = make_user(session, "codequest", role=Role.SYSTEM)
    token = create_token(system.id, Role.SYSTEM, clock.now())

    response = client.get("/api/classrooms", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_T_ACL_01_role_comes_from_database_not_from_old_token(client, session, clock):
    student = make_user(session, role=Role.STUDENT)
    stale_token = create_token(student.id, Role.PROFESSOR, clock.now())

    response = client.get("/api/classrooms", headers={"Authorization": f"Bearer {stale_token}"})

    assert response.status_code == 200


@pytest.fixture
def intruder(session, clock):
    """A second professor who must not reach the first professor's content."""
    return bearer(make_user(session, "prof_outro", role=Role.PROFESSOR), clock)


@pytest.fixture
def owner(session):
    return make_user(session, "prof_dono", role=Role.PROFESSOR)


def assert_all_404(client, headers, requests):
    for method, url, body in requests:
        response = client.request(method, url, json=body, headers=headers)
        assert response.status_code == 404, (method, url)


def test_T_ACL_02_other_professors_classroom_is_404(client, session, intruder, owner):
    classroom = make_classroom(session, owner)
    url = f"/api/professor/classrooms/{classroom.id}"

    assert_all_404(
        client,
        intruder,
        [
            ("GET", url, None),
            ("PUT", url, {"name": "Invadida"}),
            ("GET", f"{url}/missions", None),
            ("POST", f"{url}/missions", {"title": "Intrusa"}),
        ],
    )
    session.expire_all()
    assert classroom.name == "Turma"


def test_T_ACL_03_other_professors_mission_is_404(client, session, intruder, owner):
    mission = make_mission(session, make_classroom(session, owner))
    url = f"/api/professor/missions/{mission.id}"

    assert_all_404(
        client,
        intruder,
        [
            ("GET", url, None),
            ("PUT", url, {"title": "Invadida", "position": 0}),
            ("PUT", f"{url}/challenges", {"challenge_ids": []}),
            ("POST", f"{url}/publish", None),
            ("POST", f"{url}/unpublish", None),
            ("DELETE", url, None),
        ],
    )


def test_T_ACL_03_base_missions_are_404_for_professors(client, session, intruder):
    base = make_mission(session)

    response = client.get(f"/api/professor/missions/{base.id}", headers=intruder)

    assert response.status_code == 404


def test_T_ACL_04_other_professors_challenge_is_404(client, session, intruder, owner):
    challenge = make_challenge(session, owner)
    url = f"/api/professor/challenges/{challenge.id}"
    edit = {
        "title": "Invadido",
        "statement": challenge.statement,
        "type": challenge.type,
        "content": challenge.content,
    }

    assert_all_404(
        client,
        intruder,
        [
            ("GET", url, None),
            ("PUT", url, edit),
            ("POST", f"{url}/duplicate", None),
            ("POST", f"{url}/publish", None),
            ("POST", f"{url}/unpublish", None),
            ("DELETE", url, None),
        ],
    )
    assert client.get("/api/professor/challenges", headers=intruder).json() == []


def test_T_ACL_05_non_member_gets_404_on_a_turma_mission(client, session, clock):
    outsider = make_user(session, role=Role.STUDENT)
    mission = make_mission(session, make_classroom(session))
    challenge = make_challenge(session, missions=(mission,))
    headers = bearer(outsider, clock)

    assert client.get(f"/api/missions/{mission.id}", headers=headers).status_code == 404
    assert client.get(f"/api/challenges/{challenge.id}", headers=headers).status_code == 404
    submission = client.post(
        f"/api/challenges/{challenge.id}/submissions",
        json={"answer": CORRECT_ANSWER[challenge.type]},
        headers=headers,
    )
    assert submission.status_code == 404


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/me"),
        ("put", "/api/me/settings"),
        ("get", "/api/missions"),
        ("get", "/api/missions/1"),
        ("get", "/api/challenges/1"),
        ("post", "/api/challenges/1/submissions"),
        ("get", "/api/daily-challenge"),
    ],
)
def test_T_ACL_06_professor_gets_403_on_student_play_routes(client, session, clock, method, path):
    teacher = make_user(session, role=Role.PROFESSOR)

    response = client.request(method, path, headers=bearer(teacher, clock))

    assert response.status_code == 403
