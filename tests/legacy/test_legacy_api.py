"""Characterization tests of TCC1 behavior; they protect the refactor (rewritten later)."""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.legacy

PASSWORD = "Secret123"


def _register(client, email="student@example.com", role="student", name="Ana Silva"):
    return client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": PASSWORD, "role": role},
    )


def _token(client, email="student@example.com"):
    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _professor_headers(client):
    _register(client, "prof@example.com", "professor", "Prof Teste")
    return _token(client, "prof@example.com")


CHALLENGE = {
    "title": "Ordene",
    "description": "Ordene os passos",
    "difficulty": 2,
    "category": "algorithm",
    "type": "ordering",
    "content": {"items": ["a", "b", "c"], "correct_order": ["a", "b", "c"]},
}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_register_and_login(client):
    r = _register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "student@example.com"
    assert body["role"] == "student"
    assert body["xp"] == 0
    assert (
        "access_token"
        in client.post(
            "/auth/login", json={"email": "student@example.com", "password": PASSWORD}
        ).json()
    )


def test_login_wrong_password(client):
    _register(client)
    r = client.post("/auth/login", json={"email": "student@example.com", "password": "nope"})
    assert r.status_code == 401


def test_create_and_list_challenge(client):
    headers = _professor_headers(client)
    r = client.post("/challenges/", json=CHALLENGE, headers=headers)
    assert r.status_code == 201
    listing = client.get("/challenges/", headers=headers)
    assert listing.status_code == 200
    assert [c["title"] for c in listing.json()] == ["Ordene"]


def test_student_cannot_create_challenge(client):
    _register(client)
    r = client.post("/challenges/", json=CHALLENGE, headers=_token(client))
    assert r.status_code == 403


def test_submit_correct_answer_grants_xp(client):
    prof = _professor_headers(client)
    challenge_id = client.post("/challenges/", json=CHALLENGE, headers=prof).json()["id"]
    _register(client)
    with patch("app.api.submissions.feedback_agent", AsyncMock(return_value="Muito bem!")):
        r = client.post(
            "/submissions/",
            json={"challenge_id": challenge_id, "answer": {"order": ["a", "b", "c"]}},
            headers=_token(client),
        )
    assert r.status_code == 201
    body = r.json()
    assert body["is_correct"] is True
    assert body["attempt_number"] == 1
    assert body["xp_earned"] > 0
    assert body["ai_feedback"] == "Muito bem!"


def test_users_me(client):
    _register(client)
    r = client.get("/users/me", headers=_token(client))
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "student@example.com"
    assert body["level"] == 1
    assert body["badges"] == []


def test_users_me_requires_auth(client):
    assert client.get("/users/me").status_code in (401, 403)
