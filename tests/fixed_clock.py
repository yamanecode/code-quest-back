from datetime import date, datetime, timedelta

from app.core.clock import TIMEZONE


class FixedClock:
    """Clock frozen at a given instant; tests move it with set() and advance()."""

    def __init__(self, now: datetime) -> None:
        self.set(now)

    def set(self, now: datetime) -> None:
        if now.tzinfo is None:
            raise ValueError("FixedClock needs a timezone-aware datetime")
        self._now = now.astimezone(TIMEZONE)

    def advance(self, delta: timedelta) -> None:
        self._now += delta

    def now(self) -> datetime:
        return self._now

    def today(self) -> date:
        return self._now.date()
