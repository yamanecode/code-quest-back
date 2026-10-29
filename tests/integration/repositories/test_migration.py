from sqlalchemy import Engine, inspect

from tests.integration.factories import make_user

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


def test_T_MIG_02_users_have_the_recovery_code_columns(engine: Engine):
    columns = {column["name"]: column for column in inspect(engine).get_columns("users")}

    assert columns["recovery_code_hash"]["nullable"]
    assert columns["recovery_code_created_at"]["nullable"]
    assert not columns["recovery_code_confirmed"]["nullable"]


def test_T_RECOV_15_an_account_made_before_the_feature_has_no_code(session):
    user = make_user(session, "antiga")
    session.commit()
    session.refresh(user)

    assert user.recovery_code_hash is None
    assert user.recovery_code_created_at is None
    assert user.recovery_code_confirmed is False
