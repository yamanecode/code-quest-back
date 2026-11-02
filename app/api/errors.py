from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.exceptions import (
    BadRequest,
    Conflict,
    Forbidden,
    NotFound,
    RateLimited,
    ServiceError,
    ServiceUnavailable,
    Unauthorized,
    ValidationFailed,
)

STATUS_BY_ERROR: dict[type[ServiceError], int] = {
    BadRequest: 400,
    NotFound: 404,
    Unauthorized: 401,
    Forbidden: 403,
    Conflict: 409,
    ValidationFailed: 422,
    RateLimited: 429,
    ServiceUnavailable: 503,
}

HTTP_ERRORS: dict[int, tuple[str, str]] = {
    401: ("unauthorized", "É preciso entrar na conta."),
    403: ("forbidden", "Você não tem permissão para esta ação."),
    404: ("not_found", "Recurso não encontrado."),
    405: ("method_not_allowed", "Método não permitido."),
}

# PT-BR names of the request fields, for the 422 sentences of malformed requests.
FIELD_LABELS: dict[str, str] = {
    "username": "nome de usuário",
    "password": "senha",
    "new_password": "nova senha",
    "recovery_code": "código de recuperação",
    "answer": "resposta",
    "title": "título",
    "statement": "enunciado",
    "type": "tipo",
    "content": "conteúdo",
    "explanation": "explicação",
    "name": "nome",
    "weekly_goal": "meta semanal",
    "join_code": "código da turma",
    "description": "descrição",
    "position": "posição",
    "challenge_ids": "desafios",
    "mission_ids": "missões",
    "mission_id": "missão",
    "classroom_id": "turma",
    "topic": "tema",
    "profile_public": "perfil público",
    "period": "período",
    "scope": "escopo",
}
UNKNOWN_FIELD_LABEL = "um dos campos"


def field_label(loc: tuple) -> str:
    # Walk from the end: in ("body", "challenge_ids", 2) the field is before the list index.
    for part in reversed(loc):
        if isinstance(part, str) and part in FIELD_LABELS:
            return FIELD_LABELS[part]
    return UNKNOWN_FIELD_LABEL


def field_errors(exc: RequestValidationError) -> list[str]:
    sentences = (f"Campo obrigatório ou inválido: {field_label(e['loc'])}." for e in exc.errors())
    return list(dict.fromkeys(sentences))


def error_body(code: str, message: str) -> dict:
    return {"detail": code, "message": message}


async def handle_service_error(request: Request, exc: ServiceError) -> JSONResponse:
    body = error_body(exc.code, exc.message)
    headers = None
    if isinstance(exc, ValidationFailed) and exc.errors:
        body["errors"] = exc.errors
    if isinstance(exc, RateLimited):
        body["retry_after"] = exc.retry_after
        headers = {"Retry-After": str(exc.retry_after)}
    status = next(code for cls, code in STATUS_BY_ERROR.items() if isinstance(exc, cls))
    return JSONResponse(body, status_code=status, headers=headers)


async def handle_request_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Only field names are reported: echoing the input back could leak a password.
    body = error_body("validation_error", "Dados inválidos.")
    body["errors"] = field_errors(exc)
    return JSONResponse(body, status_code=422)


async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code, message = HTTP_ERRORS.get(exc.status_code, ("http_error", "Erro na requisição."))
    return JSONResponse(error_body(code, message), status_code=exc.status_code)


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # The server still logs the traceback; the client never sees internal details.
    body = error_body("internal_error", "Ocorreu um erro inesperado. Tente de novo.")
    return JSONResponse(body, status_code=500)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ServiceError, handle_service_error)
    app.add_exception_handler(RequestValidationError, handle_request_validation)
    app.add_exception_handler(StarletteHTTPException, handle_http_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
