from fastapi import APIRouter

from app.api.deps import Auth
from app.api.schemas.auth import (
    Credentials,
    RecoveryCodeOut,
    RegisterOut,
    ResetPasswordIn,
    TokenOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201)
def register(body: Credentials, auth: Auth) -> RegisterOut:
    registration = auth.register_student(body.username, body.password)
    account = registration.account
    return RegisterOut(
        id=account.id,
        username=account.username,
        role=account.role,
        recovery_code=registration.recovery_code,
    )


@router.post("/login")
def login(body: Credentials, auth: Auth) -> TokenOut:
    result = auth.login(body.username, body.password)
    return TokenOut(access_token=result.access_token, role=result.role)


@router.post("/reset-password")
def reset_password(body: ResetPasswordIn, auth: Auth) -> RecoveryCodeOut:
    code = auth.reset_password(body.username, body.recovery_code, body.new_password)
    return RecoveryCodeOut(recovery_code=code)
