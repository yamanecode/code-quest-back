from sqlalchemy import Engine, inspect

SPEC_TABLES = {
    "users",
    "classrooms",
    "classroom_members",
    "missions",
    "challenges",
    "mission_challenges",
    "submissions",
    "xp_events",
    "hint_events",
    "daily_assignments",
    "class_goal_rewards",
    "badges",
    "user_badges",
}


def test_T_MIG_01_baseline_creates_exactly_the_spec_tables(engine: Engine):
    tables = set(inspect(engine).get_table_names()) - {"alembic_version"}
    assert tables == SPEC_TABLES
