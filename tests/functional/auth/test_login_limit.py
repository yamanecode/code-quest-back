import time

import httpx
import pytest

from tests.functional.helpers import (
    STUDENT_PASSWORD,
    assert_error,
    login,
    new_client,
    register,
    unique,
)

pytestmark = pytest.mark.functional

MAX_ATTEMPTS = 5


def try_login(username: str, password: str) -> httpx.Response:
    with new_client() as client:
        return client.post("/api/auth/login", json={"username": username, "password": password})


def assert_locked(response: httpx.Response) -> None:
    body = assert_error(response, 429, "too_many_attempts")
    assert isinstance(body["retry_after"], int) and body["retry_after"] > 0, body
    assert int(response.headers["Retry-After"]) > 0


@pytest.mark.req("SG-16")
def test_FT_AUTH_14_sixth_login_after_five_failures_is_refused():
    username = unique()
    register(username)

    for _ in range(MAX_ATTEMPTS):
        assert_error(try_login(username, "senha-errada-1"), 401, "invalid_credentials")

    assert_locked(try_login(username, STUDENT_PASSWORD))
    other = unique()
    register(other)
    assert try_login(other, STUDENT_PASSWORD).status_code == 200


@pytest.mark.req("SG-16")
def test_FT_AUTH_15_unknown_username_gets_the_same_answer():
    username = unique()

    for _ in range(MAX_ATTEMPTS):
        assert_error(try_login(username, STUDENT_PASSWORD), 401, "invalid_credentials")

    assert_locked(try_login(username, STUDENT_PASSWORD))


@pytest.mark.req("SG-16")
def test_FT_AUTH_16_password_reset_ends_earlier_sessions():
    username = unique()
    code = register(username)["recovery_code"]
    old_session = login(username, STUDENT_PASSWORD)
    assert old_session.client.get("/api/me").status_code == 200
    # Token times have whole-second precision; a login in the same second stays valid.
    time.sleep(1.1)

    with new_client() as client:
        response = client.post(
            "/api/auth/reset-password",
            json={"username": username, "recovery_code": code, "new_password": "nova-senha-321"},
        )
    assert response.status_code == 200, response.text

    assert_error(old_session.client.get("/api/me"), 401)
    new_session = login(username, "nova-senha-321")
    assert new_session.client.get("/api/me").status_code == 200
    old_session.client.close()
    new_session.client.close()
