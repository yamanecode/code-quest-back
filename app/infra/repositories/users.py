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
