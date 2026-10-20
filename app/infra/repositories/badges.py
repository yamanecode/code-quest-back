from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import badges as domain_badges
from app.infra.db.models import Badge, UserBadge


class BadgeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def sync(self, definitions: Iterable[domain_badges.Badge]) -> None:
        """Insert or update the badge rows so they match the definitions in code."""
        existing = {badge.code: badge for badge in self.session.scalars(select(Badge))}
        for definition in definitions:
            row = existing.get(definition.code) or Badge(code=definition.code)
            row.name = definition.name
            row.description = definition.description
            row.tier = definition.tier
            row.emoji = definition.emoji
            row.hidden = definition.hidden
            self.session.add(row)
        self.session.flush()

    def list_all(self) -> list[Badge]:
        return list(self.session.scalars(select(Badge).order_by(Badge.id)))

    def earned(self, user_id: int) -> dict[str, datetime]:
        """Code -> moment it was earned."""
        query = (
            select(Badge.code, UserBadge.created_at)
            .join(UserBadge, UserBadge.badge_id == Badge.id)
            .where(UserBadge.user_id == user_id)
        )
        return {code: earned_at for code, earned_at in self.session.execute(query)}

    def award(self, user_id: int, codes: Iterable[str], created_at: datetime) -> None:
        badges = self.session.scalars(select(Badge).where(Badge.code.in_(list(codes))))
        for badge in badges:
            self.session.add(UserBadge(user_id=user_id, badge_id=badge.id, created_at=created_at))
        self.session.flush()
