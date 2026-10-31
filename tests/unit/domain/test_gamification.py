from datetime import UTC, datetime

import pytest

from app.domain.gamification import (
    TIMEZONE,
    TITLE_STEPS,
    RankedRow,
    RankingPeriod,
    RankRow,
    completed_every_mission,
    completion_pct,
    dense_rank,
    goal_reached,
    goal_target,
    level_for,
    mission_completed,
    month_start,
    period_start,
    solved_in_every_mission,
    title_for,
    week_start,
    window_around,
    xp_for_wrong_attempts,
    xp_to_next_level,
)


@pytest.mark.parametrize(("wrong", "xp"), [(0, 10), (1, 5), (2, 5), (3, 2), (40, 2)])
def test_T_DOM_XP_01_xp_by_wrong_attempts_before_the_solve(wrong, xp):
    assert xp_for_wrong_attempts(wrong) == xp


def test_T_DOM_XP_02_negative_attempts_are_rejected():
    with pytest.raises(ValueError):
        xp_for_wrong_attempts(-1)


def test_T_DOM_LEVEL_01_level_grows_every_30_xp():
    assert [level_for(xp) for xp in (0, 29, 30, 279, 280, 300)] == [1, 1, 2, 10, 10, 11]


def test_T_DOM_LEVEL_02_xp_to_next_level():
    assert [xp_to_next_level(xp) for xp in (0, 1, 29, 30, 280)] == [30, 29, 1, 30, 20]


@pytest.mark.parametrize(
    ("levels", "title"),
    [
        ((1, 2), "Iniciante"),
        ((3, 4), "Aprendiz"),
        ((5, 7), "Praticante"),
        ((8, 10), "Especialista"),
        ((11, 40), "Mestre"),
    ],
)
def test_T_DOM_TITLE_01_title_by_level_band(levels, title):
    assert {title_for(level) for level in levels} == {title}


@pytest.mark.parametrize(
    ("xp", "title"), [(0, "Iniciante"), (29, "Iniciante"), (279, "Especialista"), (300, "Mestre")]
)
def test_T_DOM_TITLE_02_title_from_xp(xp, title):
    assert title_for(level_for(xp)) == title


def test_T_DOM_TITLE_STEPS_01_five_ordered_bands_without_gaps():
    assert TITLE_STEPS == (
        ("Iniciante", 1, 2),
        ("Aprendiz", 3, 4),
        ("Praticante", 5, 7),
        ("Especialista", 8, 10),
        ("Mestre", 11, None),
    )


def test_T_DOM_RANK_01_week_starts_monday_midnight_in_sao_paulo():
    monday = datetime(2026, 10, 19, tzinfo=TIMEZONE)
    assert week_start(datetime(2026, 10, 21, 15, 0, tzinfo=TIMEZONE)) == monday
    assert week_start(monday) == monday
    assert week_start(datetime(2026, 10, 25, 23, 59, tzinfo=TIMEZONE)) == monday
    sunday_night_local = datetime(2026, 10, 19, 2, 0, tzinfo=UTC)
    assert week_start(sunday_night_local) == datetime(2026, 10, 12, tzinfo=TIMEZONE)
    assert week_start(monday).tzinfo == TIMEZONE
    with pytest.raises(ValueError):
        week_start(datetime(2026, 10, 21))


def test_T_DOM_RANK_02_month_starts_day_1_midnight_in_sao_paulo():
    first = datetime(2026, 10, 1, tzinfo=TIMEZONE)
    assert month_start(datetime(2026, 10, 31, 23, 59, tzinfo=TIMEZONE)) == first
    assert month_start(first) == first
    last_night_local = datetime(2026, 11, 1, 1, 0, tzinfo=UTC)
    assert month_start(last_night_local) == first


def test_T_DOM_RANK_03_dense_rank_with_ties_listed_by_username():
    rows = [
        RankRow(user_id=1, username="caio", xp=20),
        RankRow(user_id=2, username="ana", xp=30),
        RankRow(user_id=3, username="bia", xp=20),
        RankRow(user_id=4, username="duda", xp=0),
    ]

    assert dense_rank(rows) == [
        RankedRow(position=1, user_id=2, username="ana", xp=30),
        RankedRow(position=2, user_id=3, username="bia", xp=20),
        RankedRow(position=2, user_id=1, username="caio", xp=20),
        RankedRow(position=3, user_id=4, username="duda", xp=0),
    ]
    assert dense_rank([]) == []


def ranking(size: int) -> list[RankedRow]:
    rows = [RankRow(user_id=i, username=f"user{i:02d}", xp=100 - i) for i in range(1, size + 1)]
    return dense_rank(rows)


def test_T_DOM_RANK_04_window_in_the_middle_shows_two_above_and_two_below():
    window = window_around(ranking(10), user_id=5)
    assert [row.user_id for row in window] == [3, 4, 5, 6, 7]


def test_T_DOM_RANK_05_window_is_clipped_at_top_and_bottom():
    assert [row.user_id for row in window_around(ranking(10), user_id=1)] == [1, 2, 3]
    assert [row.user_id for row in window_around(ranking(10), user_id=10)] == [8, 9, 10]
    assert [row.user_id for row in window_around(ranking(2), user_id=2)] == [1, 2]
    assert window_around(ranking(3), user_id=99) == []


def test_T_DOM_GOAL_01_automatic_target_is_max_of_10_and_5_per_member():
    assert goal_target(None, member_count=1, available=100) == 10
    assert goal_target(None, member_count=2, available=100) == 10
    assert goal_target(None, member_count=3, available=100) == 15


def test_T_DOM_GOAL_02_professor_target_wins():
    assert goal_target(7, member_count=3, available=100) == 7
    assert goal_target(40, member_count=1, available=100) == 40


def test_T_DOM_GOAL_03_target_is_capped_at_the_open_first_solves():
    assert goal_target(None, member_count=4, available=12) == 12
    assert goal_target(50, member_count=1, available=8) == 8


def test_T_DOM_GOAL_04_no_goal_when_nothing_is_available():
    assert goal_target(None, member_count=5, available=0) is None
    assert goal_target(10, member_count=5, available=0) is None


def test_T_DOM_MISSION_01_completed_only_when_every_challenge_is_solved():
    assert mission_completed([1, 2, 3], solved_ids={1, 2, 3, 9})
    assert not mission_completed([1, 2, 3], solved_ids={1, 3})


def test_T_DOM_MISSION_02_mission_without_challenges_is_never_completed():
    assert not mission_completed([], solved_ids={1, 2})


def test_T_DOM_RANK_06_period_start_by_ranking_period():
    now = datetime(2026, 10, 21, 15, 0, tzinfo=TIMEZONE)
    assert period_start(RankingPeriod.WEEK, now) == week_start(now)
    assert period_start(RankingPeriod.MONTH, now) == month_start(now)
    assert period_start("month", now) == datetime(2026, 10, 1, tzinfo=TIMEZONE)


def test_T_DOM_GOAL_05_goal_is_reached_when_progress_meets_the_target():
    assert not goal_reached(progress=9, target=10)
    assert goal_reached(progress=10, target=10)
    assert goal_reached(progress=12, target=10)


def test_T_DOM_PROGRESS_01_completion_pct_is_a_rounded_integer():
    assert completion_pct(1, 3) == 33
    assert completion_pct(2, 3) == 67
    assert completion_pct(3, 3) == 100
    assert completion_pct(1, 8) == 13  # 12.5 rounds up, not to the even 12
    assert completion_pct(0, 4) == 0


def test_T_DOM_PROGRESS_02_completion_pct_of_nobody_is_zero():
    assert completion_pct(0, 0) == 0


def test_T_DOM_MISSION_03_completed_every_mission():
    missions = [[1, 2], [3]]
    assert completed_every_mission(missions, solved_ids={1, 2, 3})
    assert not completed_every_mission(missions, solved_ids={1, 2})


def test_T_DOM_MISSION_04_no_missions_means_nothing_to_complete():
    assert not completed_every_mission([], solved_ids={1})


def test_T_DOM_EXPLORE_01_solved_in_every_mission_needs_one_solve_per_mission():
    missions = [[1, 2], [3], [4, 5]]
    assert solved_in_every_mission(missions, {2, 3, 4})
    assert not solved_in_every_mission(missions, {1, 2, 3})
    assert not solved_in_every_mission([], {1})
    # A mission without published challenges cannot be explored, so it does not count.
    assert solved_in_every_mission([[1], []], {1})
