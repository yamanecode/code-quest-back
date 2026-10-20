from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.domain.enums import HintSource
from app.infra.db.models import HintEvent


@dataclass(frozen=True)
class HintUsage:
    count: int
    last_shown_at: datetime | None


class HintRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self,
        user_id: int,
        challenge_id: int,
        source: HintSource,
        level: int,
        text: str,
        discarded_count: int,
        created_at: datetime,
    ) -> HintEvent:
        event = HintEvent(
            user_id=user_id,
            challenge_id=challenge_id,
            source=source,
            level=level,
            text=text,
            discarded_count=discarded_count,
            created_at=created_at,
        )
        self.session.add(event)
        self.session.flush()
        return event

    def _own(self, user_id: int, challenge_id: int):
        return HintEvent.user_id == user_id, HintEvent.challenge_id == challenge_id

    def requested_hints(self, user_id: int, challenge_id: int) -> HintUsage:
        """Hints shown on request (they count toward the cap and the cooldown)."""
        query = select(func.count(), func.max(HintEvent.created_at)).where(
            *self._own(user_id, challenge_id), HintEvent.source == HintSource.REQUEST
        )
        count, last_shown_at = self.session.execute(query).one()
        return HintUsage(count=count, last_shown_at=last_shown_at)

    def requested_challenge_ids(self, user_id: int) -> set[int]:
        """Challenges on which the student asked for a hint (automatic hints don't count)."""
        query = select(HintEvent.challenge_id).where(
            HintEvent.user_id == user_id, HintEvent.source == HintSource.REQUEST
        )
        return set(self.session.scalars(query))

    def requested_count(self, user_id: int, challenge_ids: Iterable[int]) -> int:
        query = select(func.count()).where(
            HintEvent.user_id == user_id,
            HintEvent.challenge_id.in_(list(challenge_ids)),
            HintEvent.source == HintSource.REQUEST,
        )
        return self.session.scalar(query) or 0

    def after_wrong_hint_exists(self, user_id: int, challenge_id: int) -> bool:
        condition = exists().where(
            *self._own(user_id, challenge_id), HintEvent.source == HintSource.AFTER_WRONG
        )
        return bool(self.session.scalar(select(condition)))

    def shown_texts(self, user_id: int, challenge_id: int) -> list[str]:
        query = (
            select(HintEvent.text)
            .where(*self._own(user_id, challenge_id))
            .order_by(HintEvent.created_at, HintEvent.id)
        )
        return list(self.session.scalars(query))
