from datetime import UTC, date, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from app.core.config import settings


class Clock(Protocol):
    def now(self) -> datetime:
        """Current time as a tz-aware UTC datetime."""
        ...

    def today_local(self) -> date:
        """Current date in APP_TIMEZONE."""
        ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def today_local(self) -> date:
        return self.now().astimezone(ZoneInfo(settings.APP_TIMEZONE)).date()


class FixedClock:
    """Settable/advanceable clock for tests."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
        if self._now.tzinfo is None:
            raise ValueError("FixedClock requires a tz-aware datetime")

    def now(self) -> datetime:
        return self._now

    def today_local(self) -> date:
        return self._now.astimezone(ZoneInfo(settings.APP_TIMEZONE)).date()

    def set(self, value: datetime) -> None:
        if value.tzinfo is None:
            raise ValueError("FixedClock requires a tz-aware datetime")
        self._now = value

    def advance(self, **kwargs: float) -> None:
        self._now += timedelta(**kwargs)
