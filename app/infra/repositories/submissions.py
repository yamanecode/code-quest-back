from datetime import date, datetime

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.infra.db.models import Submission
from app.infra.repositories.local_time import day_start, local_date_of


class SubmissionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self, user_id: int, challenge_id: int, answer: dict, is_correct: bool, created_at: datetime
    ) -> Submission:
        submission = Submission(
            user_id=user_id,
            challenge_id=challenge_id,
            answer=answer,
            is_correct=is_correct,
            created_at=created_at,
        )
        self.session.add(submission)
        self.session.flush()
        return submission

    def _correct(self, user_id: int):
        return select(Submission.challenge_id).where(
            Submission.user_id == user_id, Submission.is_correct.is_(True)
        )

    def solved_challenge_ids(self, user_id: int) -> set[int]:
        return set(self.session.scalars(self._correct(user_id)))

    def has_solved(self, user_id: int, challenge_id: int) -> bool:
        solved = self._correct(user_id).where(Submission.challenge_id == challenge_id)
        return bool(self.session.scalar(select(exists(solved))))

    def solved_before(self, user_id: int, day: date) -> set[int]:
        query = self._correct(user_id).where(Submission.created_at < day_start(day))
        return set(self.session.scalars(query))

    def wrong_attempts(self, user_id: int, challenge_id: int) -> int:
        """Wrong submissions on the challenge; a solved challenge takes no more (all came first)."""
        query = select(func.count()).where(
            Submission.user_id == user_id,
            Submission.challenge_id == challenge_id,
            Submission.is_correct.is_(False),
        )
        return self.session.scalar(query) or 0

    def solve_days(self, user_id: int) -> set[date]:
        day = local_date_of(Submission.created_at)
        query = (
            select(day)
            .where(Submission.user_id == user_id, Submission.is_correct.is_(True))
            .distinct()
        )
        return set(self.session.scalars(query))
