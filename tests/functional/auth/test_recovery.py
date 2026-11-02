import re

import httpx
import pytest

from tests.functional.helpers import (
    STUDENT_PASSWORD,
    Account,
    assert_error,
    join,
    login,
    new_client,
    register,
    solve,
    turma_with_mission,
    unique,
)

pytestmark = pytest.mark.functional

CODE_FORMAT = re.compile(r"^[2-9A-HJ-NP-Z]{4}(-[2-9A-HJ-NP-Z]{4}){3}$")
NEW_PASSWORD = "outra-senha-456"


def plain(code: str) -> str:
    return code.replace("-", "")


def reset(client: httpx.Client, username: str, code: str, password: str = NEW_PASSWORD):
    return client.post(
        "/api/auth/reset-password",
        json={"username": username, "recovery_code": code, "new_password": password},
    )


def login_status(username: str, password: str) -> int:
    with new_client() as client:
        response = client.post("/api/auth/login", json={"username": username, "password": password})
    return response.status_code


def new_code(student: Account, password: str = STUDENT_PASSWORD) -> httpx.Response:
    return student.client.post("/api/me/recovery-code", json={"password": password})


@pytest.mark.req("RF-23")
def test_FT_AUTH_10_recovery_code_resets_the_password_once(anonymous):
    username = unique()
    code = register(username)["recovery_code"]
    assert CODE_FORMAT.match(code), code
    assert len(plain(code)) == 16

    response = reset(anonymous, username, plain(code).lower())

    assert response.status_code == 200, response.text
    replacement = response.json()["recovery_code"]
    assert CODE_FORMAT.match(replacement) and replacement != code
    assert login_status(username, STUDENT_PASSWORD) == 401
    assert login(username, NEW_PASSWORD).role == "student"
    assert_error(reset(anonymous, username, code, "mais-uma-senha-789"), 400, "invalid_recovery")
    assert_error(reset(anonymous, username, replacement, "curta"), 422)
    assert reset(anonymous, username, replacement, "mais-uma-senha-789").status_code == 200


@pytest.mark.req("RF-23")
@pytest.mark.req("SG-15")
def test_FT_AUTH_11_reset_answers_the_same_for_every_mismatch(anonymous):
    username = unique()
    code = register(username)["recovery_code"]
    other_code = register(unique())["recovery_code"]

    answers = [
        reset(anonymous, username, other_code),
        reset(anonymous, unique(), code),
        reset(anonymous, "ft_prof", code),
    ]

    bodies = [assert_error(response, 400, "invalid_recovery") for response in answers]
    assert bodies[0] == bodies[1] == bodies[2]
    assert login_status(username, STUDENT_PASSWORD) == 200


@pytest.mark.req("RF-23")
def test_FT_AUTH_12_new_code_needs_the_password_and_replaces_the_old_one(anonymous):
    username = unique()
    first_code = register(username)["recovery_code"]
    student = login(username, STUDENT_PASSWORD)
    for _ in range(2):
        confirmed = student.client.post("/api/me/recovery-code/confirm")
        assert confirmed.status_code == 204, confirmed.text
    assert student.client.get("/api/me").json()["recovery_code_confirmed"] is True

    assert_error(new_code(student, "senha-errada-9"), 403, "invalid_password")
    response = new_code(student)

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"recovery_code", "created_at"}
    assert CODE_FORMAT.match(body["recovery_code"]) and body["recovery_code"] != first_code
    assert student.client.get("/api/me").json()["recovery_code_confirmed"] is False
    assert_error(reset(anonymous, username, first_code), 400, "invalid_recovery")
    assert reset(anonymous, username, body["recovery_code"]).status_code == 200
    student.client.close()


@pytest.mark.req("SG-15")
def test_FT_AUTH_13_code_appears_only_where_it_is_issued(professor: Account):
    username = unique()
    code = register(username)["recovery_code"]
    student = login(username, STUDENT_PASSWORD)
    turma = turma_with_mission(professor, ("pattern",))
    join(student, turma.join_code)
    challenge_id = turma.challenges[0]["id"]
    with new_client() as anonymous:
        login_response = anonymous.post(
            "/api/auth/login", json={"username": username, "password": STUDENT_PASSWORD}
        )

    responses = [
        login_response,
        student.client.get("/api/me"),
        student.client.put("/api/me/settings", json={"profile_public": True}),
        student.client.get(f"/api/players/{username}"),
        student.client.post("/api/me/recovery-code/confirm"),
        student.client.get("/api/me/continue"),
        student.client.get("/api/classrooms"),
        student.client.get("/api/missions"),
        student.client.get(f"/api/missions/{turma.mission['id']}"),
        student.client.get(f"/api/challenges/{challenge_id}"),
        student.client.post(f"/api/challenges/{challenge_id}/hints"),
        student.client.get("/api/rankings", params={"scope": "global", "period": "week"}),
        professor.client.get(f"/api/professor/classrooms/{turma.id}/progress"),
    ]
    responses.append(student.client.post("/api/challenges/999999999/submissions", json={}))
    solve(student, turma.challenges[0])

    for response in responses:
        assert response.status_code < 500, response.text
        assert code not in response.text and plain(code) not in response.text, response.text
    me = student.client.get("/api/me").json()
    assert me["recovery_code_active"] is True
    assert me["recovery_code_created_at"]
    assert me["recovery_code_confirmed"] is True
    assert "recovery_code" not in me
    student.client.close()
