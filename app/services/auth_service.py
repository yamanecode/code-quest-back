from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.domain.accounts import account_errors, normalize_username
from app.domain.enums import Role
from app.infra.repositories.users import UserRepository
from app.infra.security import (
    InvalidToken,
    create_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.services.exceptions import Conflict, Unauthorized, ValidationFailed


@dataclass(frozen=True)
class Account:
    id: int
    username: str
    role: Role


@dataclass(frozen=True)
class LoginResult:
    access_token: str
    role: Role


def _invalid_credentials() -> Unauthorized:
    return Unauthorized("invalid_credentials", "Usuário ou senha incorretos.")


class AuthService:
    def __init__(self, session: Session, clock: Clock) -> None:
        self.session = session
        self.clock = clock
        self.users = UserRepository(session)

    def register_student(self, username: str, password: str) -> Account:
        return self._create_account(username, password, Role.STUDENT)

    def create_professor(self, username: str, password: str) -> Account:
        return self._create_account(username, password, Role.PROFESSOR)

    def _create_account(self, username: str, password: str, role: Role) -> Account:
        username = normalize_username(username)
        errors = account_errors(username, password)
        if errors:
            raise ValidationFailed(errors=errors)
        if self.users.get_by_username(username):
            raise Conflict("username_taken", "Este nome de usuário já está em uso.")
        user = self.users.add(username, hash_password(password), role)
        self.session.commit()
        return Account(user.id, user.username, user.role)

    def login(self, username: str, password: str) -> LoginResult:
        user = self.users.get_by_username(normalize_username(username))
        # Same error for every case, so the response never tells which usernames exist.
        if user is None or user.role == Role.SYSTEM:
            raise _invalid_credentials()
        if not verify_password(password, user.password_hash):
            raise _invalid_credentials()
        token = create_token(user.id, user.role, self.clock.now())
        return LoginResult(access_token=token, role=user.role)

    def current_user(self, token: str) -> Account:
        try:
            claims = decode_token(token, self.clock.now())
        except InvalidToken:
            raise Unauthorized() from None
        # The role comes from the database, so a stale token cannot keep an old role.
        user = self.users.get(claims.user_id)
        if user is None or user.role == Role.SYSTEM:
            raise Unauthorized()
        return Account(user.id, user.username, user.role)
