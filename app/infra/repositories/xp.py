from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.domain.enums import Role, XPReason
from app.infra.db.models import Challenge, ClassroomMember, Mission, MissionChallenge, User, XPEvent
from app.infra.repositories.local_time import day_end, day_start

FIRST_TRY_XP = 10


@dataclass(frozen=True)
class UserXP:
    user_id: int
    username: str
    profile_public: bool
    xp: int


class XPRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, user_id: int, challenge_id: int, amount: int, created_at: datetime) -> XPEvent:
        event = XPEvent(
            user_id=user_id,
            challenge_id=challenge_id,
            amount=amount,
            reason=XPReason.FIRST_SOLVE,
            created_at=created_at,
        )
        self.session.add(event)
        self.session.flush()
        return event

    def xp_total(self, user_id: int) -> int:
        query = select(func.coalesce(func.sum(XPEvent.amount), 0)).where(XPEvent.user_id == user_id)
        return self.session.scalar(query)

    def _xp_per_user(self, users_filter, event_filter) -> list[UserXP]:
        """Every selected user with the sum of their matching events (0 when none)."""
        xp = func.coalesce(func.sum(XPEvent.amount), 0)
        query = (
            select(User.id, User.username, User.profile_public, xp)
            .outerjoin(XPEvent, and_(XPEvent.user_id == User.id, event_filter))
            .where(users_filter)
            .group_by(User.id)
            .order_by(User.username)
        )
        return [UserXP(*row) for row in self.session.execute(query)]

    def xp_by_user_since(
        self, since: datetime, user_ids: Iterable[int] | None = None
    ) -> list[UserXP]:
        users_filter = User.role == Role.STUDENT
        if user_ids is not None:
            users_filter = and_(users_filter, User.id.in_(list(user_ids)))
        return self._xp_per_user(users_filter, XPEvent.created_at >= since)

    def _xp_in_classroom(self, classroom_id: int, *event_filters) -> list[UserXP]:
        """Members of the turma with the XP of events on challenges of its missions."""
        members = select(ClassroomMember.user_id).where(
            ClassroomMember.classroom_id == classroom_id
        )
        turma_challenges = (
            select(MissionChallenge.challenge_id)
            .join(Mission, Mission.id == MissionChallenge.mission_id)
            .where(Mission.classroom_id == classroom_id)
        )
        event_filter = and_(XPEvent.challenge_id.in_(turma_challenges), *event_filters)
        return self._xp_per_user(User.id.in_(members), event_filter)

    def xp_in_classroom_since(self, classroom_id: int, since: datetime) -> list[UserXP]:
        return self._xp_in_classroom(classroom_id, XPEvent.created_at >= since)

    def xp_in_classroom_total(self, classroom_id: int) -> list[UserXP]:
        return self._xp_in_classroom(classroom_id)

    def first_solve_types_on(self, user_id: int, day: date) -> set[str]:
        query = (
            select(Challenge.type)
            .join(XPEvent, XPEvent.challenge_id == Challenge.id)
            .where(
                XPEvent.user_id == user_id,
                XPEvent.created_at >= day_start(day),
                XPEvent.created_at < day_end(day),
            )
            .distinct()
        )
        return {str(challenge_type) for challenge_type in self.session.scalars(query)}

    def first_try_solves(self, user_id: int) -> int:
        query = select(func.count()).where(
            XPEvent.user_id == user_id, XPEvent.amount == FIRST_TRY_XP
        )
        return self.session.scalar(query) or 0

    def first_solves_by_type(self, user_id: int) -> dict[str, int]:
        query = (
            select(Challenge.type, func.count())
            .join(XPEvent, XPEvent.challenge_id == Challenge.id)
            .where(XPEvent.user_id == user_id)
            .group_by(Challenge.type)
        )
        return {str(challenge_type): total for challenge_type, total in self.session.execute(query)}
