import logging
import threading
from datetime import date

from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.core.ports import LLMClient, LLMLimitReached
from app.infra.repositories.llm_usage import LLMUsageRepository

logger = logging.getLogger(__name__)


class DailyLimitedLLMClient:
    """Wraps another client and allows at most `limit` model calls per local day.

    A call is counted before it is made, in a short transaction on its own session, so
    nothing pending in the caller's session is committed with it and no lock is held while
    the model answers. A call that fails still counts: the limit is about spending.
    """

    def __init__(
        self, inner: LLMClient, limit: int, sessions: sessionmaker[Session], clock: Clock
    ) -> None:
        self.inner = inner
        self.limit = limit
        self.sessions = sessions
        self.clock = clock
        self._logged_day: date | None = None
        self._log_lock = threading.Lock()

    def complete(
        self, system: str, user: str, *, max_tokens: int, timeout_seconds: float | None = None
    ) -> str:
        day = self.clock.today()
        if not self._take_call(day):
            self._log_limit_once(day)
            raise LLMLimitReached("daily model call limit reached")
        return self.inner.complete(
            system, user, max_tokens=max_tokens, timeout_seconds=timeout_seconds
        )

    def _take_call(self, day: date) -> bool:
        with self.sessions() as session:
            allowed = LLMUsageRepository(session).take_call(day, self.limit)
            session.commit()
        return allowed

    def _log_limit_once(self, day: date) -> None:
        with self._log_lock:
            if self._logged_day == day:
                return
            self._logged_day = day
        logger.warning("Daily model call limit reached (%d calls)", self.limit)
