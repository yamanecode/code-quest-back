from dataclasses import dataclass

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.domain.challenge_types import ChallengeType
from app.domain.enums import ContentStatus, Origin
from app.infra.db.models import Challenge, Submission

RAG_EXAMPLES = 3


@dataclass(frozen=True)
class SolveStats:
    attempted: int
    solved: int


class ChallengeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self,
        owner_id: int,
        title: str,
        statement: str,
        challenge_type: ChallengeType,
        content: dict,
        explanation: str | None,
        origin: Origin,
        status: ContentStatus = ContentStatus.DRAFT,
    ) -> Challenge:
        challenge = Challenge(
            owner_id=owner_id,
            title=title,
            statement=statement,
            type=challenge_type,
            content=content,
            explanation=explanation,
            origin=origin,
            status=status,
        )
        self.session.add(challenge)
        self.session.flush()
        return challenge

    def get(self, challenge_id: int) -> Challenge | None:
        return self.session.get(Challenge, challenge_id)

    def list_by_owner(self, owner_id: int) -> list[Challenge]:
        query = select(Challenge).where(Challenge.owner_id == owner_id).order_by(Challenge.id)
        return list(self.session.scalars(query))

    def owned_ids(self, owner_id: int, challenge_ids: list[int]) -> set[int]:
        query = select(Challenge.id).where(
            Challenge.owner_id == owner_id, Challenge.id.in_(challenge_ids)
        )
        return set(self.session.scalars(query))

    def delete(self, challenge: Challenge) -> None:
        self.session.delete(challenge)
        self.session.flush()

    def published_examples(
        self, owner_id: int, challenge_type: ChallengeType, limit: int = RAG_EXAMPLES
    ) -> list[Challenge]:
        """The owner's newest published challenges of one type (light RAG, spec §6.6)."""
        query = (
            select(Challenge)
            .where(
                Challenge.owner_id == owner_id,
                Challenge.type == challenge_type,
                Challenge.status == ContentStatus.PUBLISHED,
            )
            .order_by(Challenge.created_at.desc(), Challenge.id.desc())
            .limit(limit)
        )
        return list(self.session.scalars(query))

    def solve_stats(self, challenge_id: int) -> SolveStats:
        solved_users = func.count(Submission.user_id.distinct()).filter(
            Submission.is_correct.is_(True)
        )
        query = select(func.count(Submission.user_id.distinct()), solved_users).where(
            Submission.challenge_id == challenge_id
        )
        attempted, solved = self.session.execute(query).one()
        return SolveStats(attempted=attempted, solved=solved)

    def has_submissions(self, challenge_id: int) -> bool:
        query = select(exists().where(Submission.challenge_id == challenge_id))
        return bool(self.session.scalar(query))
