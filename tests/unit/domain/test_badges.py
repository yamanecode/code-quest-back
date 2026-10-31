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
        "level_3": ("Aprendiz", Tier.BRONZE, "🧭", False),
        "level_6": ("Praticante", Tier.SILVER, "🧭", False),
        "level_11": ("Mestre", Tier.GOLD, "🧭", False),
        "mission_1": ("Primeira missão", Tier.BRONZE, "🚩", False),
        "mission_5": ("Cinco missões", Tier.SILVER, "🚩", False),
        "mission_10": ("Dez missões", Tier.GOLD, "🚩", False),
        "first_try_5": ("Precisão", Tier.BRONZE, "🎯", False),
        "first_try_30": ("Precisão afiada", Tier.GOLD, "🎯", False),
        "class_goal_1": ("Trabalho em equipe", Tier.BRONZE, "🤝", False),
        "class_goal_5": ("Equipe afinada", Tier.SILVER, "🤝", False),
        "all_types_day": ("Pensamento completo", Tier.GOLD, "🌈", True),
        "persistent": ("Persistente", Tier.GOLD, "💪", True),
        "explorer_base": ("Viajante", Tier.GOLD, "🗺️", True),
    }

    actual = {badge.code: (badge.name, badge.tier, badge.emoji, badge.hidden) for badge in BADGES}

    assert len(BADGES) == 26
    assert actual == expected
    assert list(actual) == list(expected)
    assert all(badge.description for badge in BADGES)


def test_T_DOM_BADGE_00_requires_class_marks_gold_grades_and_class_goals():
    requires_class = {badge.code for badge in BADGES if badge.requires_class}

    assert requires_class == {
        "skill_ordering_15",
        "skill_grouping_15",
        "skill_filtering_15",
        "skill_pattern_15",
        "level_11",
        "mission_10",
        "first_try_30",
        "class_goal_1",
        "class_goal_5",
    }
    assert not any(badge.requires_class for badge in BADGES if badge.hidden)


def test_T_DOM_BADGE_00_nothing_is_earned_without_progress():
    assert badge_codes_earned(BadgeStats()) == set()


# Badges earned when one number of the student reaches a threshold: (code, stat, threshold).
THRESHOLDS = [
    ("first_solve", "solved_total", 1),
    ("level_3", "level", 3),
    ("level_6", "level", 6),
    ("level_11", "level", 11),
    ("mission_1", "missions_completed", 1),
    ("mission_5", "missions_completed", 5),
    ("mission_10", "missions_completed", 10),
    ("first_try_5", "first_try_solves", 5),
    ("first_try_30", "first_try_solves", 30),
    ("class_goal_1", "goals_contributed", 1),
    ("class_goal_5", "goals_contributed", 5),
    ("persistent", "persistent_solves", 1),
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


def test_T_DOM_BADGE_05_explorer_needs_every_base_mission():
    check(
        "explorer_base",
        BadgeStats(explored_every_base_mission=False),
        BadgeStats(explored_every_base_mission=True),
    )
