from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text

from app.core.config import get_settings
from tests.integration.factories import make_user

ALEMBIC_INI = Path(__file__).resolve().parents[3] / "alembic.ini"
BEFORE_PUBLISHED_AT = "d4e8a1b6c593"

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


def test_T_MIG_03_users_have_password_changed_at(engine: Engine):
    columns = {column["name"]: column for column in inspect(engine).get_columns("users")}

    assert columns["password_changed_at"]["nullable"]


def test_T_MIG_04_missions_and_challenges_have_published_at(engine: Engine):
    for table in ("missions", "challenges"):
        columns = {column["name"]: column for column in inspect(engine).get_columns(table)}
        assert columns["published_at"]["nullable"]


def _alembic() -> Config:
    config = Config(str(ALEMBIC_INI))
    url = get_settings().TEST_DATABASE_URL
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def test_T_MIG_05_upgrade_backfills_published_at_and_drops_old_badges(engine: Engine, session):
    session.close()
    command.downgrade(_alembic(), BEFORE_PUBLISHED_AT)
    try:
        with engine.begin() as db:
            db.execute(
                text(
                    "INSERT INTO users (id, username, password_hash, role, profile_public,"
                    " recovery_code_confirmed) VALUES (1, 'ana', 'x', 'student', false, false)"
                )
            )
            db.execute(
                text(
                    "INSERT INTO missions (id, title, position, status, created_at) VALUES"
                    " (1, 'pub', 0, 'published', '2026-10-01T12:00:00+00'),"
                    " (2, 'draft', 1, 'draft', '2026-10-02T12:00:00+00')"
                )
            )
            db.execute(
                text(
                    "INSERT INTO badges (id, code, name, description, tier, emoji, hidden) VALUES"
                    " (1, 'streak_3', 'x', 'x', 'bronze', 'x', false),"
                    " (2, 'level_5', 'x', 'x', 'silver', 'x', false),"
                    " (3, 'first_solve', 'x', 'x', 'bronze', 'x', false)"
                )
            )
            db.execute(
                text("INSERT INTO user_badges (user_id, badge_id) VALUES (1, 1), (1, 2), (1, 3)")
            )
    finally:
        command.upgrade(_alembic(), "head")

    with engine.connect() as db:
        published = dict(db.execute(text("SELECT title, published_at FROM missions")).all())
        codes = set(db.execute(text("SELECT code FROM badges")).scalars())
        earned = set(
            db.execute(
                text("SELECT b.code FROM user_badges u JOIN badges b ON b.id = u.badge_id")
            ).scalars()
        )

    assert published["pub"].isoformat().startswith("2026-10-01T")
    assert published["draft"] is None
    assert codes == {"first_solve"}
    assert earned == {"first_solve"}
