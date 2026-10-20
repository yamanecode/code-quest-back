from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.domain.hints import HINT_MAX_LEVEL, cooldown_left, hint_level, hints_left

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))


@pytest.mark.parametrize(("shown", "level"), [(0, 1), (1, 2), (2, 3), (3, 3), (4, 3)])
def test_T_DOM_HINT_01_level_grows_with_requested_hints_and_stops_at_3(shown, level):
    assert HINT_MAX_LEVEL == 3
    assert hint_level(shown) == level


@pytest.mark.parametrize(("shown", "left"), [(0, 5), (4, 1), (5, 0), (7, 0)])
def test_T_DOM_HINT_02_hints_left_never_negative(shown, left):
    assert hints_left(5, shown) == left


def test_T_DOM_HINT_03_no_cooldown_before_the_first_requested_hint():
    assert cooldown_left(None, NOW, 15) == 0


@pytest.mark.parametrize(
    ("elapsed", "left"),
    [(timedelta(0), 15), (timedelta(seconds=14.2), 1), (timedelta(seconds=15), 0)],
)
def test_T_DOM_HINT_04_cooldown_rounds_up_to_whole_seconds(elapsed, left):
    assert cooldown_left(NOW - elapsed, NOW, 15) == left


def test_T_DOM_HINT_04_cooldown_long_over_is_zero():
    assert cooldown_left(NOW - timedelta(hours=2), NOW, 15) == 0
