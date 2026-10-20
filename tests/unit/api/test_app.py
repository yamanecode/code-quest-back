import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.main import create_app
from app.services.exceptions import (
    Conflict,
    Forbidden,
    NotFound,
    RateLimited,
    ServiceError,
    ServiceUnavailable,
    Unauthorized,
    ValidationFailed,
)


class Payload(BaseModel):
    name: str


def build_client(error: ServiceError | None = None) -> TestClient:
    app = create_app()

    @app.get("/test/raise")
    def raise_error():
        raise error

    @app.post("/test/body")
    def needs_body(payload: Payload):
        return payload

    return TestClient(app)


def test_T_HEALTH_01_health_answers_ok():
    response = build_client().get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (NotFound("invalid_join_code", "Código de turma inválido."), 404),
        (Unauthorized("invalid_credentials", "Usuário ou senha incorretos."), 401),
        (Forbidden(), 403),
        (Conflict("username_taken", "Este nome de usuário já está em uso."), 409),
        (ValidationFailed("invalid_challenge", "Desafio inválido."), 422),
    ],
)
def test_T_API_ERR_01_service_errors_have_code_and_message(error, status):
    response = build_client(error).get("/test/raise")

    assert response.status_code == status
    assert response.json() == {"detail": error.code, "message": error.message}


def test_T_API_ERR_01_default_messages_are_portuguese():
    response = build_client(NotFound()).get("/test/raise")

    assert response.json() == {"detail": "not_found", "message": "Recurso não encontrado."}


def test_T_API_ERR_02_rate_limited_has_retry_after():
    error = RateLimited("hint_cooldown", "Aguarde para pedir outra dica.", retry_after=12)

    response = build_client(error).get("/test/raise")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "12"
    assert response.json() == {
        "detail": "hint_cooldown",
        "message": "Aguarde para pedir outra dica.",
        "retry_after": 12,
    }


def test_T_API_ERR_03_validation_failed_lists_rule_errors():
    error = ValidationFailed(errors=["O enunciado deve ter entre 20 e 600 caracteres."])

    response = build_client(error).get("/test/raise")

    assert response.status_code == 422
    assert response.json() == {
        "detail": "validation_error",
        "message": "Dados inválidos.",
        "errors": ["O enunciado deve ter entre 20 e 600 caracteres."],
    }


def test_T_API_ERR_04_malformed_request_body_uses_same_shape():
    response = build_client().post("/test/body", json={"wrong": 1})

    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == "validation_error"
    assert body["message"] == "Dados inválidos."


def test_T_API_ERR_05_unknown_route_uses_same_shape():
    response = build_client().get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"detail": "not_found", "message": "Recurso não encontrado."}


def test_T_API_ERR_06_wrong_method_uses_same_shape():
    response = build_client().delete("/health")

    assert response.status_code == 405
    assert response.json() == {"detail": "method_not_allowed", "message": "Método não permitido."}


def test_T_API_ERR_07_service_unavailable_is_503():
    error = ServiceUnavailable("ai_unavailable", "A IA não está disponível agora.")

    response = build_client(error).get("/test/raise")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "ai_unavailable",
        "message": "A IA não está disponível agora.",
    }


def test_T_CORS_01_only_frontend_origin_is_allowed():
    client = build_client()
    preflight = {"Access-Control-Request-Method": "GET"}

    allowed = client.options("/health", headers={"Origin": "http://localhost:3000", **preflight})
    denied = client.options("/health", headers={"Origin": "http://evil.example", **preflight})

    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in denied.headers
