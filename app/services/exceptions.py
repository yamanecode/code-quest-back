class ServiceError(Exception):
    """Base of every error a service may raise; the API layer maps it to an HTTP response."""

    default_code = "error"
    default_message = "Não foi possível concluir a operação."

    def __init__(self, code: str | None = None, message: str | None = None) -> None:
        self.code = code or self.default_code
        self.message = message or self.default_message
        super().__init__(self.code)


class BadRequest(ServiceError):
    default_code = "bad_request"
    default_message = "Requisição inválida."


class NotFound(ServiceError):
    default_code = "not_found"
    default_message = "Recurso não encontrado."


class Unauthorized(ServiceError):
    default_code = "unauthorized"
    default_message = "É preciso entrar na conta."


class Forbidden(ServiceError):
    default_code = "forbidden"
    default_message = "Você não tem permissão para esta ação."


class Conflict(ServiceError):
    default_code = "conflict"
    default_message = "A operação conflita com o estado atual."


class ValidationFailed(ServiceError):
    default_code = "validation_error"
    default_message = "Dados inválidos."

    def __init__(
        self, code: str | None = None, message: str | None = None, errors: list[str] | None = None
    ) -> None:
        super().__init__(code, message)
        self.errors = errors or []


class RateLimited(ServiceError):
    default_code = "rate_limited"
    default_message = "Aguarde um pouco antes de tentar de novo."

    def __init__(
        self, code: str | None = None, message: str | None = None, *, retry_after: int
    ) -> None:
        super().__init__(code, message)
        self.retry_after = retry_after


class ServiceUnavailable(ServiceError):
    default_code = "unavailable"
    default_message = "Serviço indisponível no momento. Tente de novo mais tarde."
