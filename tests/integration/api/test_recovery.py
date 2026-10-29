import logging

import pytest
from sqlalchemy import select

from app.domain.enums import Role
from app.domain.recovery_code import format_recovery_code, is_well_formed
from app.infra.db.models import User
from app.infra.security import hash_recovery_code
from app.services.auth_service import AuthService
from tests.integration.factories import make_user

PASSWORD = "segredo123"
NEW_PASSWORD = "outra-senha-9"
INVALID_RECOVERY = {
    "detail": "invalid_recovery",
    "message": "Usuário ou código de recuperação inválido.",
}


def register(client, username="aluna"):
    response = client.post("/api/auth/register", json={"username": username, "password": PASSWORD})
    assert response.status_code == 201
    return response.json()["recovery_code"]


def login(client, username="aluna", password=PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def auth_header(client, username="aluna", password=PASSWORD):
    token = login(client, username, password).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def reset(client, username, code, new_password=NEW_PASSWORD):
    body = {"username": username, "recovery_code": code, "new_password": new_password}
    return client.post("/api/auth/reset-password", json=body)


def regenerate(client, password=PASSWORD, username="aluna"):
    return client.post(
        "/api/me/recovery-code", json={"password": password}, headers=auth_header(client, username)
    )


def stored_user(session, username="aluna"):
    return session.scalar(select(User).where(User.username == username))


def test_T_RECOV_01_register_returns_a_code_and_stores_only_its_hash(client, session):
    code = register(client)

    user = stored_user(session)
    assert is_well_formed(code)
    assert code == format_recovery_code(code.replace("-", ""))
    assert user.recovery_code_hash == hash_recovery_code(code)
    assert user.recovery_code_created_at is not None
    assert user.recovery_code_confirmed is False


def test_T_RECOV_02_the_stored_value_is_never_the_code(client, session):
    code = register(client)

    user = stored_user(session)
    stored = [user.username, user.password_hash, user.recovery_code_hash]
    assert not any(code in value or code.replace("-", "") in value for value in stored)


def test_T_RECOV_03_reset_changes_the_password(client):
    code = register(client)

    response = reset(client, "aluna", code)

    assert response.status_code == 200
    assert login(client, password=PASSWORD).status_code == 401
    assert login(client, password=NEW_PASSWORD).status_code == 200


def test_T_RECOV_04_reset_replaces_the_code(client, session):
    old_code = register(client)

    new_code = reset(client, "aluna", old_code).json()["recovery_code"]

    assert new_code != old_code
    assert is_well_formed(new_code)
    assert stored_user(session).recovery_code_confirmed is False
    assert reset(client, "aluna", old_code).json() == INVALID_RECOVERY
    assert reset(client, "aluna", new_code, "mais-uma-senha-1").status_code == 200


def test_T_RECOV_05_every_mismatch_gives_the_same_answer(client, session, clock):
    code = register(client)
    AuthService(session, clock).create_professor("prof_ana", PASSWORD)
    make_user(session, "sistema", Role.SYSTEM)
    no_code_user = make_user(session, "sem_codigo")
    session.commit()
    other_code = format_recovery_code("ABCDEFGHJKLMNPQR")

    answers = [
        reset(client, "aluna", other_code),
        reset(client, "ninguem", code),
        reset(client, "prof_ana", code),
        reset(client, "sistema", code),
        reset(client, no_code_user.username, code),
    ]

    assert {answer.status_code for answer in answers} == {400}
    assert all(answer.json() == INVALID_RECOVERY for answer in answers)
    assert login(client, password=PASSWORD).status_code == 200


@pytest.mark.parametrize(
    "style", [str.lower, lambda code: code.replace("-", ""), lambda c: f" {c} "]
)
def test_T_RECOV_06_the_code_may_be_typed_in_any_style(client, style):
    code = register(client)

    assert reset(client, "aluna", style(code)).status_code == 200


def test_T_RECOV_06_the_username_is_case_insensitive(client):
    code = register(client)

    assert reset(client, "ALUNA", code).status_code == 200


def test_T_RECOV_07_a_bad_new_password_is_rejected_and_the_code_stays_valid(client):
    code = register(client)

    response = reset(client, "aluna", code, "curta")

    assert response.status_code == 422
    assert response.json()["detail"] == "validation_error"
    assert login(client, password=PASSWORD).status_code == 200
    assert reset(client, "aluna", code).status_code == 200


def test_T_RECOV_08_regenerate_needs_the_password_and_replaces_the_code(client, session):
    old_code = register(client)

    denied = regenerate(client, "senha-errada")
    assert denied.status_code == 403
    assert denied.json()["detail"] == "invalid_password"
    assert stored_user(session).recovery_code_hash == hash_recovery_code(old_code)

    granted = regenerate(client)
    new_code = granted.json()["recovery_code"]

    assert granted.status_code == 200
    assert granted.json()["created_at"]
    assert is_well_formed(new_code)
    assert stored_user(session).recovery_code_hash == hash_recovery_code(new_code)
    assert reset(client, "aluna", old_code).status_code == 400
    assert reset(client, "aluna", new_code).status_code == 200


def test_T_RECOV_08_regenerate_is_for_students_with_a_token(client, session, clock):
    AuthService(session, clock).create_professor("prof_ana", PASSWORD)

    anonymous = client.post("/api/me/recovery-code", json={"password": PASSWORD})
    professor = regenerate(client, username="prof_ana")

    assert anonymous.status_code == 401
    assert professor.status_code == 403


def test_T_RECOV_09_confirm_sets_the_flag_and_is_idempotent(client, session):
    register(client)
    headers = auth_header(client)

    first = client.post("/api/me/recovery-code/confirm", headers=headers)
    second = client.post("/api/me/recovery-code/confirm", headers=headers)

    assert (first.status_code, second.status_code) == (204, 204)
    assert stored_user(session).recovery_code_confirmed is True


def test_T_RECOV_09_a_new_code_must_be_confirmed_again(client, session):
    register(client)
    client.post("/api/me/recovery-code/confirm", headers=auth_header(client))

    regenerate(client)

    assert stored_user(session).recovery_code_confirmed is False


def test_T_RECOV_10_confirm_without_a_code_conflicts(client, session):
    register(client)
    stored_user(session).recovery_code_hash = None
    session.commit()

    response = client.post("/api/me/recovery-code/confirm", headers=auth_header(client))

    assert response.status_code == 409
    assert response.json()["detail"] == "no_recovery_code"


def test_T_RECOV_11_profile_reports_the_code_status(client, session):
    register(client)
    headers = auth_header(client)

    before = client.get("/api/me", headers=headers).json()
    client.post("/api/me/recovery-code/confirm", headers=headers)
    after = client.get("/api/me", headers=headers).json()

    assert before["recovery_code_active"] is True
    assert before["recovery_code_created_at"] is not None
    assert before["recovery_code_confirmed"] is False
    assert after["recovery_code_confirmed"] is True


def test_T_RECOV_11_an_account_without_a_code_is_reported_inactive(client, session):
    register(client)
    user = stored_user(session)
    user.recovery_code_hash = None
    user.recovery_code_created_at = None
    session.commit()

    profile = client.get("/api/me", headers=auth_header(client)).json()

    assert profile["recovery_code_active"] is False
    assert profile["recovery_code_created_at"] is None
    assert profile["recovery_code_confirmed"] is False


def test_T_RECOV_12_no_log_record_contains_a_code(client, caplog):
    caplog.set_level(logging.DEBUG)
    code = register(client)
    regenerate(client, "senha-errada")
    reset(client, "aluna", code)
    reset(client, "aluna", code)

    raw = code.replace("-", "")
    assert not any(code in line or raw in line for line in caplog.messages)


def test_T_RECOV_13_the_code_is_returned_only_by_register_reset_and_regenerate(client, session):
    code = register(client)
    headers = auth_header(client)
    bodies = [
        client.get("/api/me", headers=headers),
        client.post("/api/me/recovery-code/confirm", headers=headers),
        client.put("/api/me/settings", json={"profile_public": True}, headers=headers),
        client.get("/api/classrooms", headers=headers),
        login(client),
        reset(client, "aluna", "ABCD-EFGH-JKLM-NPQR"),
    ]
    hashed = stored_user(session).recovery_code_hash

    for response in bodies:
        assert code not in response.text
        assert hashed not in response.text
        assert 'recovery_code":' not in response.text.replace(" ", "")
    assert "recovery_code" in regenerate(client).json()


def test_T_RECOV_13_the_public_profile_has_no_recovery_data(client):
    register(client)
    headers = auth_header(client)
    client.put("/api/me/settings", json={"profile_public": True}, headers=headers)

    body = client.get("/api/players/aluna", headers=headers).json()

    assert set(body) == {"username", "level", "title", "badges"}


def test_T_RECOV_16_reset_accepts_only_its_three_fields(client):
    code = register(client)
    body = {"username": "aluna", "recovery_code": code, "new_password": NEW_PASSWORD, "x": 1}

    assert client.post("/api/auth/reset-password", json=body).status_code == 422
