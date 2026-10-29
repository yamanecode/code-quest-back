from datetime import datetime, timedelta

from app.core.attempt_limiter import AttemptLimiter
from app.core.clock import TIMEZONE

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=TIMEZONE)
KEY = ("aluna", "10.0.0.1")


def fail(limiter, key=KEY, times=1, at=NOW):
    for _ in range(times):
        limiter.record_failure(key, at)


def test_T_LIM_01_blocks_after_the_maximum_number_of_failures():
    limiter = AttemptLimiter(max_attempts=3, window_seconds=900)

    fail(limiter, times=2)
    assert limiter.check(KEY, NOW) is None

    fail(limiter)
    assert limiter.check(KEY, NOW) is not None


def test_T_LIM_02_failures_leave_the_sliding_window():
    limiter = AttemptLimiter(max_attempts=2, window_seconds=900)
    fail(limiter, at=NOW)
    fail(limiter, at=NOW + timedelta(seconds=600))
    assert limiter.check(KEY, NOW + timedelta(seconds=601)) is not None

    # The first failure is 900 s old: only one failure is left in the window.
    assert limiter.check(KEY, NOW + timedelta(seconds=900)) is None


def test_T_LIM_03_clear_forgets_the_failures():
    limiter = AttemptLimiter(max_attempts=2, window_seconds=900)
    fail(limiter, times=2)

    limiter.clear(KEY)

    assert limiter.check(KEY, NOW) is None
    limiter.clear(("nunca", "visto"))  # clearing an unknown key is harmless


def test_T_LIM_04_keys_are_independent():
    limiter = AttemptLimiter(max_attempts=1, window_seconds=900)
    fail(limiter)

    assert limiter.check(KEY, NOW) is not None
    assert limiter.check(("aluna", "10.0.0.2"), NOW) is None
    assert limiter.check(("outra", "10.0.0.1"), NOW) is None


def test_T_LIM_05_retry_after_counts_down_and_is_at_least_one():
    limiter = AttemptLimiter(max_attempts=1, window_seconds=900)
    fail(limiter, at=NOW)

    assert limiter.check(KEY, NOW) == 900
    assert limiter.check(KEY, NOW + timedelta(seconds=100)) == 800
    assert limiter.check(KEY, NOW + timedelta(seconds=899, milliseconds=500)) == 1
