from datetime import date, datetime

from app.core.clock import TIMEZONE
from app.infra.repositories.daily import DailyRepository
from tests.integration.factories import NOON, make_challenge, make_user, submit

DAY = date(2026, 10, 14)


def test_T_REPO_19_dailies_solved_counts_only_solves_on_their_own_day(session):
    ana = make_user(session)
    on_time, late, never, wrong = (make_challenge(session) for _ in range(4))
    repo = DailyRepository(session)
    repo.add(ana.id, date(2026, 10, 14), on_time.id, created_at=NOON)
    repo.add(ana.id, date(2026, 10, 15), late.id, created_at=NOON)
    repo.add(ana.id, date(2026, 10, 16), never.id, created_at=NOON)
    repo.add(ana.id, date(2026, 10, 17), wrong.id, created_at=NOON)

    submit(session, ana, on_time, True, datetime(2026, 10, 14, 23, 30, tzinfo=TIMEZONE))
    submit(session, ana, late, True, datetime(2026, 10, 16, 9, tzinfo=TIMEZONE))
    submit(session, ana, wrong, False, datetime(2026, 10, 17, 9, tzinfo=TIMEZONE))

    assert repo.dailies_solved(ana.id) == 1
