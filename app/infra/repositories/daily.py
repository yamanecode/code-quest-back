from datetime import date, datetime

from sqlalchemy import and_, exists, func, select
from sqlalchemy.orm import Session

from app.infra.db.models import DailyAssignment, Submission
from app.infra.repositories.local_time import local_date_of


class DailyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def daily_assignment(self, user_id: int, day: date) -> DailyAssignment | None:
        query = select(DailyAssignment).where(
            DailyAssignment.user_id == user_id, DailyAssignment.day == day
        )
        return self.session.scalar(query)

    def add(
        self, user_id: int, day: date, challenge_id: int, created_at: datetime
    ) -> DailyAssignment:
        assignment = DailyAssignment(
            user_id=user_id, day=day, challenge_id=challenge_id, created_at=created_at
        )
        self.session.add(assignment)
        self.session.flush()
        return assignment

    def dailies_solved(self, user_id: int) -> int:
        """Daily challenges solved on the very day they were assigned."""
        solved_that_day = exists().where(
            and_(
                Submission.user_id == DailyAssignment.user_id,
                Submission.challenge_id == DailyAssignment.challenge_id,
                Submission.is_correct.is_(True),
                local_date_of(Submission.created_at) == DailyAssignment.day,
            )
        )
        query = select(func.count()).where(DailyAssignment.user_id == user_id, solved_that_day)
        return self.session.scalar(query) or 0
