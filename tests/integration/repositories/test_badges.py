from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infra.db.models import UserBadge
from app.infra.repositories.badges import BadgeRepository
from tests.integration.factories import NOON, make_user


def test_T_REPO_BADGE_01_a_badge_awarded_meanwhile_by_another_request_is_kept_once(
    engine, session, badge_catalog
):
    ana = make_user(session, "ana")
    session.commit()
    with Session(engine) as other:  # a parallel request awards the same badge first
        BadgeRepository(other).award(ana.id, ["first_solve"], NOON)
        other.commit()

    BadgeRepository(session).award(ana.id, ["first_solve", "level_3"], NOON)
    session.commit()

    count = select(func.count()).select_from(UserBadge).where(UserBadge.user_id == ana.id)
    assert session.scalar(count) == 2
    assert set(BadgeRepository(session).earned(ana.id)) == {"first_solve", "level_3"}
