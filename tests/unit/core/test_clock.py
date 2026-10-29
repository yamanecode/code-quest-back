from datetime import timedelta
from zoneinfo import ZoneInfo

from app.core.clock import TIMEZONE, SystemClock

SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def test_T_CLOCK_01_system_clock_is_aware_in_sao_paulo():
    clock = SystemClock()

    now = clock.now()

    assert TIMEZONE == SAO_PAULO
    assert now.tzinfo == SAO_PAULO
    assert clock.today() in {now.date(), now.date() + timedelta(days=1)}
