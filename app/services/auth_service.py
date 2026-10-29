from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.domain.accounts import account_errors, normalize_username, password_errors
from app.domain.enums import Role
from app.domain.recovery_code import format_recovery_code
from app.infra.repositories.users import UserRepository
from app.infra.security import (
    InvalidToken,
    create_token,
    decode_token,
    generate_recovery_code,
    hash_password,
    hash_recovery_code,
    recovery_code_matches,
    verify_password,
)
from app.services.exceptions import (
    BadRequest,
    Conflict,
    Forbidden,
    NotFound,
    Unauthorized,
    ValidationFailed,
)


@dataclass(frozen=True)
class Account:
    id: int
    username: str
    role: Role


@dataclass(frozen=True)
class Registration:
    account: Account
    recovery_code: str


@dataclass(frozen=True)
class IssuedCode:
    recovery_code: str
    created_at: datetime


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

    def register_student(self, username: str, password: str) -> Registration:
        account = self._create_account(username, password, Role.STUDENT)
        code = self._issue_recovery_code(account.id)
        self.session.commit()
        return Registration(account, code)

    def create_professor(self, username: str, password: str) -> Account:
        account = self._create_account(username, password, Role.PROFESSOR)
        self.session.commit()
        return account

    def _create_account(self, username: str, password: str, role: Role) -> Account:
        username = normalize_username(username)
        errors = account_errors(username, password)
        if errors:
            raise ValidationFailed(errors=errors)
        if self.users.get_by_username(username):
            raise Conflict("username_taken", "Este nome de usuário já está em uso.")
        user = self.users.add(username, hash_password(password), role)
        return Account(user.id, user.username, user.role)

    def _issue_recovery_code(self, user_id: int) -> str:
        """Replaces the user's code and returns the new one, the only time it is visible."""
        raw = generate_recovery_code()
        self.users.set_recovery_code(
            self.users.get(user_id), hash_recovery_code(raw), self.clock.now()
        )
        return format_recovery_code(raw)

    def reset_password(self, username: str, recovery_code: str, new_password: str) -> str:
        """Sets a new password with the recovery code; returns the replacement code."""
        # Only the password format is checked here; the username is checked by the lookup below.
        errors = password_errors(new_password)
        if errors:
            raise ValidationFailed(errors=errors)
        user = self.users.get_by_username(normalize_username(username))
        if (
            user is None
            or user.role != Role.STUDENT
            or user.recovery_code_hash is None
            or not recovery_code_matches(recovery_code, user.recovery_code_hash)
        ):
            raise BadRequest("invalid_recovery", "Usuário ou código de recuperação inválido.")
        self.users.set_password_hash(user, hash_password(new_password))
        code = self._issue_recovery_code(user.id)
        self.session.commit()
        return code

    def regenerate_recovery_code(self, user_id: int, password: str) -> IssuedCode:
        user = self.users.get(user_id)
        if not verify_password(password, user.password_hash):
            raise Forbidden("invalid_password", "Senha incorreta.")
        code = self._issue_recovery_code(user_id)
        self.session.commit()
        return IssuedCode(code, user.recovery_code_created_at)

    def confirm_recovery_code(self, user_id: int) -> None:
        user = self.users.get(user_id)
        if user.recovery_code_hash is None:
            raise Conflict("no_recovery_code", "Esta conta ainda não tem um código de recuperação.")
        self.users.confirm_recovery_code(user)
        self.session.commit()

    def reset_password_as_admin(self, username: str, new_password: str) -> None:
        """Command-line reset for a professor or a student who lost both password and code."""
        username = normalize_username(username)
        errors = account_errors(username, new_password)
        if errors:
            raise ValidationFailed(errors=errors)
        user = self.users.get_by_username(username)
        if user is None or user.role == Role.SYSTEM:
            raise NotFound("user_not_found", "Usuário não encontrado.")
        self.users.set_password_hash(user, hash_password(new_password))
        self.session.commit()

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
