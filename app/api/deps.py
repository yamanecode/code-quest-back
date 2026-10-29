"""Dependency wiring: the only API module that knows the concrete implementations."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.clock import Clock, SystemClock
from app.core.config import get_settings
from app.core.ports import LLMClient
from app.domain.enums import Role
from app.infra.db.session import get_session
from app.infra.llm.factory import build_llm_client
from app.services.ai_service import AIService
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


@lru_cache
def get_llm_client() -> LLMClient:
    """One client per process: the HTTP adapter keeps its connection pool."""
    return build_llm_client(get_settings())


def get_auth_service(
    session: DbSession, clock: Annotated[Clock, Depends(get_clock)]
) -> AuthService:
    return AuthService(session, clock)


def get_content_service(
    session: DbSession, clock: Annotated[Clock, Depends(get_clock)]
) -> ContentService:
    return ContentService(session, clock)


def get_gamification_service(
    session: DbSession, clock: Annotated[Clock, Depends(get_clock)]
) -> GamificationService:
    return GamificationService(session, clock)


def get_classroom_service(
    session: DbSession,
    clock: Annotated[Clock, Depends(get_clock)],
    gamification: Annotated[GamificationService, Depends(get_gamification_service)],
) -> ClassroomService:
    return ClassroomService(session, clock, gamification)


def get_ai_service(
    session: DbSession,
    clock: Annotated[Clock, Depends(get_clock)],
    llm: Annotated[LLMClient, Depends(get_llm_client)],
    content: Annotated[ContentService, Depends(get_content_service)],
) -> AIService:
    return AIService(session, clock, llm, content, get_settings().HINT_COOLDOWN_SECONDS)


def get_play_service(
    session: DbSession,
    clock: Annotated[Clock, Depends(get_clock)],
    gamification: Annotated[GamificationService, Depends(get_gamification_service)],
    goals: Annotated[ClassroomService, Depends(get_classroom_service)],
    ai: Annotated[AIService, Depends(get_ai_service)],
) -> PlayService:
    return PlayService(session, clock, gamification, goals, ai)


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
AI = Annotated[AIService, Depends(get_ai_service)]
Auth = Annotated[AuthService, Depends(get_auth_service)]
Classrooms = Annotated[ClassroomService, Depends(get_classroom_service)]
Content = Annotated[ContentService, Depends(get_content_service)]
Gamification = Annotated[GamificationService, Depends(get_gamification_service)]
Play = Annotated[PlayService, Depends(get_play_service)]
