import pytest

from app.domain.badges import (
    BADGES,
    HIDDEN_BADGE_NAME,
    BadgeStats,
    Tier,
    badge_codes_earned,
    badge_display,
)

ALL_TYPES = frozenset({"ordering", "grouping", "filtering", "pattern"})


def check(code: str, below: BadgeStats, at: BadgeStats) -> None:
    assert code not in badge_codes_earned(below)
    assert code in badge_codes_earned(at)


def test_T_DOM_BADGE_00_catalog_matches_the_spec_table():
    expected = {
        "first_solve": ("Primeiro desafio", Tier.BRONZE, "⭐", False),
        "skill_ordering_3": ("Algoritmos I", Tier.BRONZE, "🔢", False),
        "skill_ordering_7": ("Algoritmos II", Tier.SILVER, "🔢", False),
        "skill_ordering_15": ("Algoritmos III", Tier.GOLD, "🔢", False),
        "skill_grouping_3": ("Decomposição I", Tier.BRONZE, "🧩", False),
        "skill_grouping_7": ("Decomposição II", Tier.SILVER, "🧩", False),
        "skill_grouping_15": ("Decomposição III", Tier.GOLD, "🧩", False),
        "skill_filtering_3": ("Abstração I", Tier.BRONZE, "🔍", False),
        "skill_filtering_7": ("Abstração II", Tier.SILVER, "🔍", False),
        "skill_filtering_15": ("Abstração III", Tier.GOLD, "🔍", False),
        "skill_pattern_3": ("Padrões I", Tier.BRONZE, "🔁", False),
        "skill_pattern_7": ("Padrões II", Tier.SILVER, "🔁", False),
        "skill_pattern_15": ("Padrões III", Tier.GOLD, "🔁", False),
        "level_3": ("Explorador(a)", Tier.BRONZE, "🧭", False),
        "level_5": ("Estrategista", Tier.SILVER, "🧭", False),
        "level_8": ("Arquiteto(a) de soluções", Tier.SILVER, "🧭", False),
        "level_11": ("Mestre do pensamento", Tier.GOLD, "🧭", False),
        "mission_1": ("Primeira missão", Tier.BRONZE, "🚩", False),
        "mission_5": ("Cinco missões", Tier.SILVER, "🚩", False),
        "mission_10": ("Dez missões", Tier.GOLD, "🚩", False),
        "streak_3": ("Três dias seguidos", Tier.BRONZE, "🔥", False),
        "streak_7": ("Sete dias seguidos", Tier.SILVER, "🔥", False),
        "streak_14": ("Catorze dias seguidos", Tier.GOLD, "🔥", False),
        "first_try_5": ("Precisão", Tier.SILVER, "🎯", False),
        "first_try_20": ("Precisão afiada", Tier.GOLD, "🎯", False),
        "daily_7": ("Compromisso diário", Tier.SILVER, "📅", False),
        "class_goal_1": ("Trabalho em equipe", Tier.BRONZE, "🤝", False),
        "class_goal_5": ("Equipe afinada", Tier.SILVER, "🤝", False),
        "all_types_day": ("Pensamento completo", Tier.SILVER, "🌈", True),
        "no_hint_mission": ("Por conta própria", Tier.SILVER, "🦉", True),
    }

    actual = {badge.code: (badge.name, badge.tier, badge.emoji, badge.hidden) for badge in BADGES}

    assert len(BADGES) == 30
    assert actual == expected
    assert list(actual) == list(expected)
    assert all(badge.description for badge in BADGES)


def test_T_DOM_BADGE_00_nothing_is_earned_without_progress():
    assert badge_codes_earned(BadgeStats()) == set()


# Badges earned when one number of the student reaches a threshold: (code, stat, threshold).
THRESHOLDS = [
    ("first_solve", "solved_total", 1),
    ("level_3", "level", 3),
    ("level_5", "level", 5),
    ("level_8", "level", 8),
    ("level_11", "level", 11),
    ("mission_1", "missions_completed", 1),
    ("mission_5", "missions_completed", 5),
    ("mission_10", "missions_completed", 10),
    ("streak_3", "streak", 3),
    ("streak_7", "streak", 7),
    ("streak_14", "streak", 14),
    ("first_try_5", "first_try_solves", 5),
    ("first_try_20", "first_try_solves", 20),
    ("daily_7", "dailies_solved", 7),
    ("class_goal_1", "goals_contributed", 1),
    ("class_goal_5", "goals_contributed", 5),
    ("no_hint_mission", "missions_completed_without_hints", 1),
]


@pytest.mark.parametrize(("code", "stat", "threshold"), THRESHOLDS)
def test_T_DOM_BADGE_01_earned_exactly_at_the_threshold(code, stat, threshold):
    check(code, BadgeStats(**{stat: threshold - 1}), BadgeStats(**{stat: threshold}))


@pytest.mark.parametrize("challenge_type", sorted(ALL_TYPES))
@pytest.mark.parametrize("threshold", [3, 7, 15])
def test_T_DOM_BADGE_02_skill_badges_count_only_their_own_type(challenge_type, threshold):
    other = next(t for t in sorted(ALL_TYPES) if t != challenge_type)
    check(
        f"skill_{challenge_type}_{threshold}",
        BadgeStats(solved_by_type={challenge_type: threshold - 1, other: 99}),
        BadgeStats(solved_by_type={challenge_type: threshold}),
    )


def test_T_DOM_BADGE_03_all_types_day_needs_the_four_types():
    check(
        "all_types_day",
        BadgeStats(types_first_solved_today=ALL_TYPES - {"pattern"}),
        BadgeStats(types_first_solved_today=ALL_TYPES),
    )


def test_T_DOM_BADGE_04_hidden_badge_is_secret_until_earned():
    by_code = {badge.code: badge for badge in BADGES}
    hidden, visible = by_code["all_types_day"], by_code["first_solve"]

    assert HIDDEN_BADGE_NAME == "Insígnia secreta"
    assert badge_display(hidden, earned=False) == (HIDDEN_BADGE_NAME, "")
    assert badge_display(hidden, earned=True) == (hidden.name, hidden.description)
    assert badge_display(visible, earned=False) == (visible.name, visible.description)
