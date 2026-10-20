from datetime import timedelta

import pytest
from sqlalchemy import select

from app.domain.enums import Role
from app.infra.db.models import User
from tests.integration.factories import make_user

PASSWORD = "segredo123"


def register(client, username="aluna", password=PASSWORD):
    return client.post("/api/auth/register", json={"username": username, "password": password})


def login(client, username="aluna", password=PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def stored_user(session, username):
    return session.scalar(select(User).where(User.username == username))


def test_T_AUTH_01_register_creates_student(client, session):
    response = register(client, "Aluna.01")

    assert response.status_code == 201
    body = response.json()
    assert body == {"id": body["id"], "username": "aluna.01", "role": "student"}
    assert stored_user(session, "aluna.01").role == Role.STUDENT


def test_T_AUTH_01_register_accepts_only_username_and_password(client):
    response = client.post(
        "/api/auth/register",
        json={"username": "aluna", "password": PASSWORD, "join_code": "ABC123"},
    )

    assert response.status_code == 422
    assert response.json()["errors"] == ["body.join_code"]


def test_T_AUTH_01_register_schema_has_only_username_and_password(client):
    schema = client.get("/openapi.json").json()["components"]["schemas"]["Credentials"]

    assert set(schema["properties"]) == {"username", "password"}


@pytest.mark.parametrize("second", ["aluna", "ALUNA"])
def test_T_AUTH_02_duplicate_username_conflicts(client, second):
    register(client, "aluna")

    response = register(client, second)

    assert response.status_code == 409
    assert response.json() == {
        "detail": "username_taken",
        "message": "Este nome de usuário já está em uso.",
    }


@pytest.mark.parametrize(
    ("username", "password"),
    [("ab", PASSWORD), ("ana maria", PASSWORD), ("aluna", "curta"), ("aluna", "x" * 73)],
)
def test_T_AUTH_04_invalid_username_or_password_is_rejected(client, session, username, password):
    response = register(client, username, password)

    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == "validation_error"
    assert len(body["errors"]) == 1
    assert session.scalar(select(User)) is None


def test_T_AUTH_04_missing_fields_are_rejected(client):
    response = client.post("/api/auth/register", json={"username": "aluna"})

    assert response.status_code == 422
    assert response.json()["errors"] == ["body.password"]


def test_T_AUTH_05_login_returns_bearer_token(client):
    register(client, "aluna")

    response = login(client, "Aluna")

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["role"] == "student"
    me = client.get("/api/classrooms", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200


@pytest.mark.parametrize(
    ("username", "password"), [("aluna", "senha-errada"), ("ninguem", PASSWORD)]
)
def test_T_AUTH_06_wrong_credentials_are_rejected(client, username, password):
    register(client, "aluna")

    response = login(client, username, password)

    assert response.status_code == 401
    assert response.json() == {
        "detail": "invalid_credentials",
        "message": "Usuário ou senha incorretos.",
    }


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer nao-e-um-token"}, {"Authorization": "Basic YWJjOmRlZg=="}],
)
def test_T_AUTH_07_token_required(client, headers):
    response = client.get("/api/classrooms", headers=headers)

    assert response.status_code == 401
    assert response.json()["detail"] == "unauthorized"


def test_T_AUTH_07_token_of_deleted_user_is_rejected(client, session):
    register(client, "aluna")
    token = login(client, "aluna").json()["access_token"]
    session.delete(stored_user(session, "aluna"))
    session.commit()

    response = client.get("/api/classrooms", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_T_AUTH_08_expired_token_is_rejected(client, clock):
    register(client, "aluna")
    headers = {"Authorization": f"Bearer {login(client).json()['access_token']}"}

    clock.advance(timedelta(hours=7, minutes=59))
    assert client.get("/api/classrooms", headers=headers).status_code == 200
    clock.advance(timedelta(minutes=1))
    response = client.get("/api/classrooms", headers=headers)

    assert response.status_code == 401


def test_T_AUTH_09_system_account_cannot_log_in(client, session):
    system = make_user(session, "codequest", role=Role.SYSTEM)
    system.password_hash = "!"
    session.flush()

    response = login(client, "codequest", "!")

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_credentials"


def test_T_AUTH_HASH_password_is_stored_as_bcrypt_and_never_returned(client, session):
    registered = register(client, "aluna")
    logged = login(client, "aluna")

    password_hash = stored_user(session, "aluna").password_hash
    assert password_hash.startswith("$2b$12$")
    assert password_hash != PASSWORD
    for response in (registered, logged):
        assert PASSWORD not in response.text
        assert password_hash not in response.text
