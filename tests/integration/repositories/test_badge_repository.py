from app.domain.badges import BADGES
from app.infra.repositories.badges import BadgeRepository
from tests.integration.factories import NOON, make_user


def test_T_REPO_27_sync_is_idempotent_and_awards_are_listed(session):
    repo = BadgeRepository(session)
    repo.sync(BADGES)
    repo.sync(BADGES)
    assert [badge.code for badge in repo.list_all()] == [badge.code for badge in BADGES]

    ana = make_user(session)
    repo.award(ana.id, {"first_solve", "streak_3"}, created_at=NOON)

    assert repo.earned(ana.id) == {"first_solve": NOON, "streak_3": NOON}
    assert repo.earned(make_user(session).id) == {}
