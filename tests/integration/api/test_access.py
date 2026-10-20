import pytest
from fastapi import Depends

from app.api.deps import require_professor
from app.api.routers import professor
from app.domain.enums import Role
from app.infra.security import create_token
from tests.integration.auth_helpers import bearer
from tests.integration.factories import make_user

PROBE = "/api/professor/probe"


@pytest.fixture
def probe_client(client):
    # B3 has no professor endpoint yet; this route uses the same guard as the professor router.
    @client.app.get(PROBE, dependencies=[Depends(require_professor)])
    def probe():
        return {"ok": True}

    return client


def test_T_ACL_01_professor_router_requires_professor_role():
    guards = [dependency.dependency for dependency in professor.router.dependencies]

    assert require_professor in guards


def test_T_ACL_01_student_gets_403_on_professor_routes(probe_client, session, clock):
    student = make_user(session, role=Role.STUDENT)

    response = probe_client.get(PROBE, headers=bearer(student, clock))

    assert response.status_code == 403
    assert response.json()["detail"] == "forbidden"


def test_T_ACL_01_professor_passes_the_professor_guard(probe_client, session, clock):
    teacher = make_user(session, role=Role.PROFESSOR)

    response = probe_client.get(PROBE, headers=bearer(teacher, clock))

    assert response.status_code == 200


def test_T_ACL_01_professor_route_without_token_is_401(probe_client):
    assert probe_client.get(PROBE).status_code == 401


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
