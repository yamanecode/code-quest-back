"""Dependency wiring: the only API module that knows the concrete implementations."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.clock import Clock, SystemClock
from app.domain.enums import Role
from app.infra.db.session import get_session
from app.services.auth_service import Account, AuthService
from app.services.classroom_service import ClassroomService
from app.services.content_service import ContentService
from app.services.exceptions import Forbidden, Unauthorized
from app.services.gamification_service import GamificationService
from app.services.play_service import PlayService

bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_session)]


def get_clock() -> Clock:
    return SystemClock()


def get_auth_service(
    session: DbSession, clock: Annotated[Clock, Depends(get_clock)]
) -> AuthService:
    return AuthService(session, clock)


def get_classroom_service(session: DbSession) -> ClassroomService:
    return ClassroomService(session)


def get_content_service(session: DbSession) -> ContentService:
    return ContentService(session)


def get_gamification_service(
    session: DbSession, clock: Annotated[Clock, Depends(get_clock)]
) -> GamificationService:
    return GamificationService(session, clock)


def get_play_service(
    session: DbSession,
    clock: Annotated[Clock, Depends(get_clock)],
    gamification: Annotated[GamificationService, Depends(get_gamification_service)],
) -> PlayService:
    return PlayService(session, clock, gamification)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> Account:
    if credentials is None:
        raise Unauthorized()
    return auth.current_user(credentials.credentials)


def require_student(user: Annotated[Account, Depends(get_current_user)]) -> Account:
    if user.role != Role.STUDENT:
        raise Forbidden()
    return user


def require_professor(user: Annotated[Account, Depends(get_current_user)]) -> Account:
    if user.role != Role.PROFESSOR:
        raise Forbidden()
    return user


CurrentStudent = Annotated[Account, Depends(require_student)]
CurrentProfessor = Annotated[Account, Depends(require_professor)]
Auth = Annotated[AuthService, Depends(get_auth_service)]
Classrooms = Annotated[ClassroomService, Depends(get_classroom_service)]
Content = Annotated[ContentService, Depends(get_content_service)]
Gamification = Annotated[GamificationService, Depends(get_gamification_service)]
Play = Annotated[PlayService, Depends(get_play_service)]
