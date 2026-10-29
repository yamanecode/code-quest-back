from datetime import UTC, date, datetime, timedelta

from app.core.clock import TIMEZONE
from app.infra.repositories.submissions import SubmissionRepository
from tests.integration.factories import make_challenge, make_user, submit

MIDNIGHT = datetime(2026, 10, 14, tzinfo=TIMEZONE)


def test_T_REPO_05_solved_before_uses_local_midnight(session):
    ana = make_user(session)
    late_evening = make_challenge(session)
    utc_after_midnight = make_challenge(session)
    today = make_challenge(session)
    submit(session, ana, late_evening, True, MIDNIGHT - timedelta(microseconds=1))
    # 01:00 UTC on the 14th is still 22:00 of the 13th in São Paulo.
    submit(session, ana, utc_after_midnight, True, datetime(2026, 10, 14, 1, tzinfo=UTC))
    submit(session, ana, today, True, MIDNIGHT)

    solved = SubmissionRepository(session).solved_before(ana.id, date(2026, 10, 14))
    assert solved == {late_evening.id, utc_after_midnight.id}


def test_T_REPO_06_wrong_attempts_count_only_own_wrong_submissions(session):
    ana, bia = make_user(session), make_user(session)
    challenge, other = make_challenge(session), make_challenge(session)
    for correct in (False, False, True):
        submit(session, ana, challenge, correct)
    submit(session, ana, other, correct=False)
    submit(session, bia, challenge, correct=False)

    repo = SubmissionRepository(session)
    assert repo.wrong_attempts(ana.id, challenge.id) == 2
    assert repo.has_solved(ana.id, challenge.id)
    assert not repo.has_solved(ana.id, other.id)
    assert not repo.has_solved(bia.id, challenge.id)


def test_T_REPO_07_solve_days_are_local_dates_of_correct_submissions(session):
    ana = make_user(session)
    challenge = make_challenge(session)
    # 23:30 in São Paulo is already the next day in UTC.
    submit(session, ana, challenge, True, datetime(2026, 10, 14, 23, 30, tzinfo=TIMEZONE))
    submit(session, ana, challenge, True, datetime(2026, 10, 14, 8, tzinfo=TIMEZONE))
    submit(session, ana, challenge, False, datetime(2026, 10, 16, 8, tzinfo=TIMEZONE))

    assert SubmissionRepository(session).solve_days(ana.id) == {date(2026, 10, 14)}
