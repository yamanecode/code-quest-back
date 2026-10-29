import logging
from datetime import timedelta

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.domain.enums import Role
from app.infra.db.models import User
from app.infra.security import verify_password
from app.services.auth_service import AuthService
from tests.integration.factories import make_user

PASSWORD = "segredo123"
NEW_PASSWORD = "outra-senha-9"
TOO_MANY = {
    "detail": "too_many_attempts",
    "message": "Muitas tentativas. Aguarde alguns minutos e tente de novo.",
}


def register(client, username="aluna"):
    response = client.post("/api/auth/register", json={"username": username, "password": PASSWORD})
    assert response.status_code == 201
    return response.json()["recovery_code"]


def login(client, username="aluna", password=PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def fail_logins(client, username="aluna", times=5):
    for _ in range(times):
        assert login(client, username, "senha-errada").status_code == 401


def bearer(response):
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def reset(client, username, code, new_password=NEW_PASSWORD):
    body = {"username": username, "recovery_code": code, "new_password": new_password}
    return client.post("/api/auth/reset-password", json=body)


def count_password_checks(monkeypatch):
    calls = []
    real = verify_password

    def counting(password, password_hash):
        calls.append(password_hash)
        return real(password, password_hash)

    monkeypatch.setattr("app.services.auth_service.verify_password", counting)
    return calls


def test_T_LOGIN_01_the_sixth_failure_is_blocked_even_with_the_right_password(client):
    register(client)
    fail_logins(client)

    response = login(client, password=PASSWORD)

    assert response.status_code == 429
    body = response.json()
    assert {key: body[key] for key in ("detail", "message")} == TOO_MANY
    assert 1 <= body["retry_after"] <= get_settings().LOGIN_WINDOW_SECONDS
    assert response.headers["Retry-After"] == str(body["retry_after"])


def test_T_LOGIN_02_an_unknown_username_gets_the_identical_answer(client):
    register(client)
    fail_logins(client, "aluna")
    fail_logins(client, "ninguem")

    known = login(client, "aluna")
    unknown = login(client, "ninguem")

    assert known.status_code == unknown.status_code == 429
    assert known.json() == unknown.json()


def test_T_LOGIN_03_a_successful_login_clears_the_failures(client):
    register(client)
    fail_logins(client, times=4)

    assert login(client).status_code == 200

    fail_logins(client, times=4)
    assert login(client).status_code == 200


def test_T_LOGIN_04_other_clients_and_other_usernames_are_not_blocked(client):
    register(client, "aluna")
    register(client, "bruno")
    fail_logins(client, "aluna")
    elsewhere = TestClient(client.app, client=("10.9.9.9", 5000))

    assert login(client, "aluna").status_code == 429
    assert login(client, "bruno").status_code == 200
    assert login(elsewhere, "aluna").status_code == 200


def test_T_LOGIN_04_the_username_is_normalised_for_the_counter(client):
    register(client)
    fail_logins(client, "ALUNA")

    assert login(client, "aluna").status_code == 429


def test_T_LOGIN_05_the_block_ends_when_the_window_passes(client, clock):
    register(client)
    fail_logins(client)
    assert login(client).status_code == 429

    clock.advance(timedelta(seconds=get_settings().LOGIN_WINDOW_SECONDS))

    assert login(client).status_code == 200


def test_T_LOGIN_06_a_blocked_request_does_no_password_work(client, monkeypatch):
    register(client)
    fail_logins(client)
    calls = count_password_checks(monkeypatch)

    assert login(client).status_code == 429
    assert calls == []


def test_T_LOGIN_07_nothing_about_the_attempts_is_logged(client, caplog):
    caplog.set_level(logging.DEBUG)
    register(client)
    fail_logins(client)
    login(client)

    text = " ".join(caplog.messages).lower()
    assert "aluna" not in text
    assert "too_many" not in text
    assert "attempt" not in text


def test_T_LOGIN_08_a_reset_is_not_limited_by_failed_logins(client):
    code = register(client)
    fail_logins(client)

    assert reset(client, "aluna", code).status_code == 200


def test_T_AUTH_TIME_01_unknown_and_system_usernames_still_check_a_password(
    client, session, monkeypatch
):
    register(client)
    make_user(session, "codequest", Role.SYSTEM)
    session.commit()
    calls = count_password_checks(monkeypatch)

    for username in ("aluna", "ninguem", "codequest"):
        before = len(calls)
        assert login(client, username, "senha-errada").status_code == 401
        assert len(calls) == before + 1


def test_T_SESS_01_a_token_issued_before_a_reset_stops_working(client, clock):
    code = register(client)
    old = bearer(login(client))
    assert client.get("/api/me", headers=old).status_code == 200
    clock.advance(timedelta(seconds=10))

    reset(client, "aluna", code)

    response = client.get("/api/me", headers=old)
    assert response.status_code == 401
    assert response.json()["detail"] == "unauthorized"


def test_T_SESS_02_a_token_from_a_login_after_the_reset_works(client, clock):
    code = register(client)
    clock.advance(timedelta(seconds=10))
    reset(client, "aluna", code)
    clock.advance(timedelta(seconds=5))

    fresh = bearer(login(client, password=NEW_PASSWORD))

    assert client.get("/api/me", headers=fresh).status_code == 200


def test_T_SESS_03_a_login_in_the_same_second_as_the_reset_works(client, clock):
    code = register(client)
    clock.advance(timedelta(seconds=10))
    reset(client, "aluna", code)

    same_second = bearer(login(client, password=NEW_PASSWORD))

    assert client.get("/api/me", headers=same_second).status_code == 200


def test_T_SESS_04_other_users_keep_their_sessions(client, clock):
    code = register(client, "aluna")
    register(client, "bruno")
    bruno = bearer(login(client, "bruno"))
    clock.advance(timedelta(seconds=10))

    reset(client, "aluna", code)

    assert client.get("/api/me", headers=bruno).status_code == 200


def test_T_SESS_05_the_command_line_reset_ends_sessions_too(client, session, clock):
    register(client)
    old = bearer(login(client))
    clock.advance(timedelta(seconds=10))

    AuthService(session, clock).reset_password_as_admin("aluna", NEW_PASSWORD)

    assert client.get("/api/me", headers=old).status_code == 401
    assert session.scalar(select(User)).password_changed_at is not None


def test_T_SESS_06_a_token_without_iat_is_rejected_only_after_a_password_change(
    client, session, clock
):
    code = register(client)
    claims = {
        "sub": str(session.scalar(select(User)).id),
        "role": "student",
        "exp": int((clock.now() + timedelta(hours=8)).timestamp()),
    }
    old = {"Authorization": "Bearer " + jwt.encode(claims, get_settings().JWT_SECRET, "HS256")}
    assert client.get("/api/me", headers=old).status_code == 200
    clock.advance(timedelta(seconds=10))

    reset(client, "aluna", code)

    assert client.get("/api/me", headers=old).status_code == 401
