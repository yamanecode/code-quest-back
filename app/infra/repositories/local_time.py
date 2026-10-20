from datetime import date, datetime, time, timedelta

from sqlalchemy import Date, cast, func
from sqlalchemy.sql import ColumnElement

from app.core.clock import TIMEZONE


def day_start(day: date) -> datetime:
    """Midnight of `day` in the game time zone."""
    return datetime.combine(day, time.min, tzinfo=TIMEZONE)


def day_end(day: date) -> datetime:
    return day_start(day + timedelta(days=1))


def local_date_of(column: ColumnElement[datetime]) -> ColumnElement[date]:
    """SQL expression for the local calendar date of a timestamptz column."""
    return cast(func.timezone(TIMEZONE.key, column), Date)
