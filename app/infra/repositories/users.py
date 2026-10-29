from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import Role
from app.infra.db.models import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, username: str, password_hash: str, role: Role) -> User:
        user = User(username=username, password_hash=password_hash, role=role)
        self.session.add(user)
        self.session.flush()
        return user

    def get(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        return self.session.scalar(select(User).where(User.username == username))

    def set_password_hash(self, user: User, password_hash: str) -> None:
        user.password_hash = password_hash

    def set_recovery_code(self, user: User, code_hash: str, now: datetime) -> None:
        """A new code replaces the old one and starts unconfirmed."""
        user.recovery_code_hash = code_hash
        user.recovery_code_created_at = now
        user.recovery_code_confirmed = False

    def confirm_recovery_code(self, user: User) -> None:
        user.recovery_code_confirmed = True
