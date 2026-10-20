from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.clock import TIMEZONE, FixedClock, SystemClock

SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def test_T_CLOCK_01_system_clock_is_aware_in_sao_paulo():
    clock = SystemClock()

    now = clock.now()

    assert TIMEZONE == SAO_PAULO
    assert now.tzinfo == SAO_PAULO
    assert clock.today() in {now.date(), now.date() + timedelta(days=1)}


def test_T_CLOCK_02_fixed_clock_set_and_advance():
    clock = FixedClock(datetime(2026, 10, 19, 23, 59, tzinfo=SAO_PAULO))
    assert clock.today() == date(2026, 10, 19)

    clock.advance(timedelta(minutes=1))
    assert clock.now() == datetime(2026, 10, 20, 0, 0, tzinfo=SAO_PAULO)
    assert clock.today() == date(2026, 10, 20)

    clock.set(datetime(2026, 1, 1, 12, 0, tzinfo=SAO_PAULO))
    assert clock.today() == date(2026, 1, 1)


def test_T_CLOCK_03_fixed_clock_converts_to_sao_paulo():
    utc_instant = datetime(2026, 10, 20, 2, 30, tzinfo=ZoneInfo("UTC"))

    clock = FixedClock(utc_instant)

    assert clock.now().tzinfo == SAO_PAULO
    assert clock.today() == date(2026, 10, 19)


def test_T_CLOCK_04_fixed_clock_rejects_naive_datetime():
    with pytest.raises(ValueError):
        FixedClock(datetime(2026, 10, 20, 12, 0))
