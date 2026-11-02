from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infra.db.models import LLMUsage
from app.infra.repositories.locks import lock_llm_usage


class LLMUsageRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def take_call(self, day: date, limit: int) -> bool:
        """Count one model call on `day` if fewer than `limit` were made; the caller commits.

        The advisory lock makes two requests at the last free call take turns, so only
        one of them gets it.
        """
        lock_llm_usage(self.session)
        usage = self.session.scalar(select(LLMUsage).where(LLMUsage.day == day))
        if usage is None:
            usage = LLMUsage(day=day, count=0)
            self.session.add(usage)
        if usage.count >= limit:
            return False
        usage.count += 1
        self.session.flush()
        return True
