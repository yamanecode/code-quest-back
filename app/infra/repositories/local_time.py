from datetime import date, datetime, time, timedelta

from app.core.clock import TIMEZONE


def day_start(day: date) -> datetime:
    """Midnight of `day` in the game time zone."""
    return datetime.combine(day, time.min, tzinfo=TIMEZONE)


def day_end(day: date) -> datetime:
    return day_start(day + timedelta(days=1))
