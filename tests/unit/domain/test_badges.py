from app.domain.badges import BADGES, BadgeStats, Tier, badge_codes_earned

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


def test_T_DOM_BADGE_01_first_solve():
    check("first_solve", BadgeStats(solved_total=0), BadgeStats(solved_total=1))


def test_T_DOM_BADGE_02_skill_ordering_3():
    check(
        "skill_ordering_3",
        BadgeStats(solved_by_type={"ordering": 2, "grouping": 9}),
        BadgeStats(solved_by_type={"ordering": 3}),
    )


def test_T_DOM_BADGE_03_skill_ordering_7():
    check(
        "skill_ordering_7",
        BadgeStats(solved_by_type={"ordering": 6}),
        BadgeStats(solved_by_type={"ordering": 7}),
    )


def test_T_DOM_BADGE_04_skill_ordering_15():
    check(
        "skill_ordering_15",
        BadgeStats(solved_by_type={"ordering": 14}),
        BadgeStats(solved_by_type={"ordering": 15}),
    )


def test_T_DOM_BADGE_05_skill_grouping_3():
    check(
        "skill_grouping_3",
        BadgeStats(solved_by_type={"grouping": 2, "ordering": 9}),
        BadgeStats(solved_by_type={"grouping": 3}),
    )


def test_T_DOM_BADGE_06_skill_grouping_7():
    check(
        "skill_grouping_7",
        BadgeStats(solved_by_type={"grouping": 6}),
        BadgeStats(solved_by_type={"grouping": 7}),
    )


def test_T_DOM_BADGE_07_skill_grouping_15():
    check(
        "skill_grouping_15",
        BadgeStats(solved_by_type={"grouping": 14}),
        BadgeStats(solved_by_type={"grouping": 15}),
    )


def test_T_DOM_BADGE_08_skill_filtering_3():
    check(
        "skill_filtering_3",
        BadgeStats(solved_by_type={"filtering": 2, "pattern": 9}),
        BadgeStats(solved_by_type={"filtering": 3}),
    )


def test_T_DOM_BADGE_09_skill_filtering_7():
    check(
        "skill_filtering_7",
        BadgeStats(solved_by_type={"filtering": 6}),
        BadgeStats(solved_by_type={"filtering": 7}),
    )


def test_T_DOM_BADGE_10_skill_filtering_15():
    check(
        "skill_filtering_15",
        BadgeStats(solved_by_type={"filtering": 14}),
        BadgeStats(solved_by_type={"filtering": 15}),
    )


def test_T_DOM_BADGE_11_skill_pattern_3():
    check(
        "skill_pattern_3",
        BadgeStats(solved_by_type={"pattern": 2, "filtering": 9}),
        BadgeStats(solved_by_type={"pattern": 3}),
    )


def test_T_DOM_BADGE_12_skill_pattern_7():
    check(
        "skill_pattern_7",
        BadgeStats(solved_by_type={"pattern": 6}),
        BadgeStats(solved_by_type={"pattern": 7}),
    )


def test_T_DOM_BADGE_13_skill_pattern_15():
    check(
        "skill_pattern_15",
        BadgeStats(solved_by_type={"pattern": 14}),
        BadgeStats(solved_by_type={"pattern": 15}),
    )


def test_T_DOM_BADGE_14_level_3():
    check("level_3", BadgeStats(level=2), BadgeStats(level=3))


def test_T_DOM_BADGE_15_level_5():
    check("level_5", BadgeStats(level=4), BadgeStats(level=5))


def test_T_DOM_BADGE_16_level_8():
    check("level_8", BadgeStats(level=7), BadgeStats(level=8))


def test_T_DOM_BADGE_17_level_11():
    check("level_11", BadgeStats(level=10), BadgeStats(level=11))


def test_T_DOM_BADGE_18_mission_1():
    check("mission_1", BadgeStats(missions_completed=0), BadgeStats(missions_completed=1))


def test_T_DOM_BADGE_19_mission_5():
    check("mission_5", BadgeStats(missions_completed=4), BadgeStats(missions_completed=5))


def test_T_DOM_BADGE_20_mission_10():
    check("mission_10", BadgeStats(missions_completed=9), BadgeStats(missions_completed=10))


def test_T_DOM_BADGE_21_streak_3():
    check("streak_3", BadgeStats(streak=2), BadgeStats(streak=3))


def test_T_DOM_BADGE_22_streak_7():
    check("streak_7", BadgeStats(streak=6), BadgeStats(streak=7))


def test_T_DOM_BADGE_23_streak_14():
    check("streak_14", BadgeStats(streak=13), BadgeStats(streak=14))


def test_T_DOM_BADGE_24_first_try_5():
    check("first_try_5", BadgeStats(first_try_solves=4), BadgeStats(first_try_solves=5))


def test_T_DOM_BADGE_25_first_try_20():
    check("first_try_20", BadgeStats(first_try_solves=19), BadgeStats(first_try_solves=20))


def test_T_DOM_BADGE_26_daily_7():
    check("daily_7", BadgeStats(dailies_solved=6), BadgeStats(dailies_solved=7))


def test_T_DOM_BADGE_27_class_goal_1():
    check("class_goal_1", BadgeStats(goals_contributed=0), BadgeStats(goals_contributed=1))


def test_T_DOM_BADGE_28_class_goal_5():
    check("class_goal_5", BadgeStats(goals_contributed=4), BadgeStats(goals_contributed=5))


def test_T_DOM_BADGE_29_all_types_day():
    check(
        "all_types_day",
        BadgeStats(types_first_solved_today=ALL_TYPES - {"pattern"}),
        BadgeStats(types_first_solved_today=ALL_TYPES),
    )


def test_T_DOM_BADGE_30_no_hint_mission():
    check(
        "no_hint_mission",
        BadgeStats(missions_completed=3, missions_completed_without_hints=0),
        BadgeStats(missions_completed=1, missions_completed_without_hints=1),
    )
