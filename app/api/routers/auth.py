from fastapi import APIRouter

from app.api.deps import Auth
from app.api.schemas.auth import AccountOut, Credentials, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201)
def register(body: Credentials, auth: Auth) -> AccountOut:
    account = auth.register_student(body.username, body.password)
    return AccountOut(id=account.id, username=account.username, role=account.role)


@router.post("/login")
def login(body: Credentials, auth: Auth) -> TokenOut:
    result = auth.login(body.username, body.password)
    return TokenOut(access_token=result.access_token, role=result.role)
