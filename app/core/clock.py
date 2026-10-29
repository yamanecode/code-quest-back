from datetime import date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("America/Sao_Paulo")


class Clock(Protocol):
    def now(self) -> datetime: ...

    def today(self) -> date: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(TIMEZONE)

    def today(self) -> date:
        return self.now().date()
