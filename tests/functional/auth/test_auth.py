import httpx
import pytest

from tests.functional.helpers import (
    STUDENT_PASSWORD,
    Account,
    assert_error,
    login,
    new_client,
    signup_student,
    unique,
)

pytestmark = pytest.mark.functional

PROTECTED = ["/api/me", "/api/missions", "/api/classrooms", "/api/professor/classrooms"]


def register(client: httpx.Client, username: str, password: str = STUDENT_PASSWORD):
    return client.post("/api/auth/register", json={"username": username, "password": password})


@pytest.mark.req("RF-01")
def test_FT_AUTH_01_student_signs_up_and_logs_in(anonymous):
    username = unique()

    response = register(anonymous, username)

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == username
    assert body["role"] == "student"
    assert isinstance(body["id"], int)
    login_response = anonymous.post(
        "/api/auth/login", json={"username": username, "password": STUDENT_PASSWORD}
    )
    assert login_response.status_code == 200
    assert login_response.json()["role"] == "student"


@pytest.mark.req("RF-01")
def test_FT_AUTH_02_duplicate_username_returns_409(anonymous):
    username = unique()
    assert register(anonymous, username).status_code == 201

    assert_error(register(anonymous, username), 409, "username_taken")


@pytest.mark.req("RF-01")
@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("ab", STUDENT_PASSWORD),
        ("a" * 31, STUDENT_PASSWORD),
        ("nome com espaco", STUDENT_PASSWORD),
        ("joão_silva", STUDENT_PASSWORD),
        ("aluno-hifen", STUDENT_PASSWORD),
        (None, "1234567"),
        (None, "x" * 73),
        (None, ""),
    ],
    ids=[
        "username_short",
        "username_long",
        "username_space",
        "username_accent",
        "username_hyphen",
        "password_short",
        "password_long",
        "password_empty",
    ],
)
def test_FT_AUTH_03_invalid_username_or_password_returns_422(anonymous, username, password):
    username = username or unique()

    assert_error(register(anonymous, username, password), 422)

    if username.startswith("ft_"):
        assert register(anonymous, username).status_code == 201, "the invalid sign-up was stored"


@pytest.mark.req("RF-01")
def test_FT_AUTH_04_no_endpoint_creates_a_professor(anonymous):
    spec = anonymous.get("/openapi.json").json()
    schemas = spec["components"]["schemas"]
    request_bodies = [
        operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].split("/")[-1]
        for path in spec["paths"].values()
        for operation in path.values()
        if "requestBody" in operation
    ]
    account_paths = [path for path in spec["paths"] if path.startswith("/api/auth/")]

    assert sorted(account_paths) == ["/api/auth/login", "/api/auth/register"]
    assert all("role" not in schemas[name].get("properties", {}) for name in request_bodies)

    username = unique()
    response = anonymous.post(
        "/api/auth/register",
        json={"username": username, "password": STUDENT_PASSWORD, "role": "professor"},
    )
    if response.status_code == 201:
        assert response.json()["role"] == "student"
        assert login(username, STUDENT_PASSWORD).role == "student"
    else:
        assert_error(response, 422)


@pytest.mark.req("RF-02")
def test_FT_AUTH_05_login_returns_a_bearer_token(anonymous):
    student = signup_student()

    response = anonymous.post(
        "/api/auth/login", json={"username": student.username, "password": STUDENT_PASSWORD}
    )

    body = response.json()
    assert body["token_type"] == "bearer"
    with new_client(body["access_token"]) as client:
        assert client.get("/api/me").status_code == 200
    wrong = anonymous.post(
        "/api/auth/login", json={"username": student.username, "password": "senha-errada-1"}
    )
    assert_error(wrong, 401, "invalid_credentials")
    unknown = anonymous.post(
        "/api/auth/login", json={"username": unique(), "password": STUDENT_PASSWORD}
    )
    assert_error(unknown, 401, "invalid_credentials")
    student.client.close()


@pytest.mark.req("RF-02")
def test_FT_AUTH_06_protected_endpoints_need_a_valid_token(anonymous, student: Account):
    tampered = student.token[:-4] + ("aaaa" if not student.token.endswith("aaaa") else "bbbb")

    assert anonymous.get("/health").status_code == 200
    for path in PROTECTED:
        assert_error(anonymous.get(path), 401)
        for token in ("not-a-token", tampered):
            with new_client(token) as client:
                assert_error(client.get(path), 401)


@pytest.mark.req("SG-09")
def test_FT_AUTH_07_sign_up_accepts_only_username_and_password(anonymous):
    spec = anonymous.get("/openapi.json").json()
    operation = spec["paths"]["/api/auth/register"]["post"]
    schema_name = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    schema = spec["components"]["schemas"][schema_name.split("/")[-1]]

    assert set(schema["properties"]) == {"username", "password"}
    username = unique()
    response = anonymous.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": STUDENT_PASSWORD,
            "email": "aluno@example.com",
            "name": "Nome Real",
        },
    )
    if response.status_code == 201:
        student = login(username, STUDENT_PASSWORD)
        me = student.client.get("/api/me").text
        student.client.close()
        assert "aluno@example.com" not in me
        assert "Nome Real" not in me
    else:
        assert_error(response, 422)


@pytest.mark.req("SG-09")
def test_FT_AUTH_08_no_response_contains_the_password_or_its_hash(anonymous):
    username = unique()
    password = "segredo-unico-4821"
    responses = [register(anonymous, username, password)]
    responses.append(
        anonymous.post("/api/auth/login", json={"username": username, "password": password})
    )
    with new_client(responses[1].json()["access_token"]) as client:
        responses.append(client.get("/api/me"))
        responses.append(client.put("/api/me/settings", json={"profile_public": True}))
        responses.append(client.get(f"/api/players/{username}"))

    for response in responses:
        assert response.status_code in (200, 201), response.text
        text = response.text
        assert password not in text
        assert "$2b$" not in text and "$2a$" not in text
        assert "password" not in text.lower()


@pytest.mark.req("RNF-05")
def test_FT_AUTH_09_error_responses_have_a_code_and_a_portuguese_message(
    anonymous, student: Account, professor: Account
):
    username = unique()
    register(anonymous, username)

    assert_error(anonymous.get("/api/me"), 401)
    assert_error(student.client.get("/api/professor/classrooms"), 403)
    assert_error(student.client.get("/api/missions/999999999"), 404)
    assert_error(professor.client.get("/api/professor/challenges/999999999"), 404)
    assert_error(register(anonymous, username), 409)
    assert_error(anonymous.post("/api/auth/register", json={"username": unique()}), 422)
    assert_error(anonymous.post("/api/auth/register", content=b"not json"), 422)
    assert_error(student.client.get("/api/rankings", params={"period": "year"}), 422)
