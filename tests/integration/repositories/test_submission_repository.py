from datetime import UTC, date, datetime, timedelta

from app.core.clock import TIMEZONE
from app.infra.repositories.submissions import SubmissionRepository
from tests.integration.factories import make_challenge, make_user, submit

MIDNIGHT = datetime(2026, 10, 14, tzinfo=TIMEZONE)


def test_T_REPO_04_solved_challenge_ids_only_correct_and_own(session):
    ana, bia = make_user(session), make_user(session)
    solved, wrong_only, other = (make_challenge(session) for _ in range(3))
    submit(session, ana, solved, correct=False)
    submit(session, ana, solved, correct=True)
    submit(session, ana, wrong_only, correct=False)
    submit(session, bia, other, correct=True)

    assert SubmissionRepository(session).solved_challenge_ids(ana.id) == {solved.id}


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


def test_T_REPO_06_wrong_attempts_before_first_solve(session):
    ana, bia = make_user(session), make_user(session)
    challenge = make_challenge(session)
    unsolved = make_challenge(session)
    for correct in (False, False, True, False):
        submit(session, ana, challenge, correct)
    for _ in range(3):
        submit(session, ana, unsolved, correct=False)
    submit(session, bia, challenge, correct=False)

    repo = SubmissionRepository(session)
    assert repo.wrong_attempts_before_first_solve(ana.id, challenge.id) == 2
    assert repo.wrong_attempts_before_first_solve(ana.id, unsolved.id) == 3
    assert repo.wrong_attempts_before_first_solve(bia.id, unsolved.id) == 0


def test_T_REPO_07_solve_days_are_local_dates_of_correct_submissions(session):
    ana = make_user(session)
    challenge = make_challenge(session)
    # 23:30 in São Paulo is already the next day in UTC.
    submit(session, ana, challenge, True, datetime(2026, 10, 14, 23, 30, tzinfo=TIMEZONE))
    submit(session, ana, challenge, True, datetime(2026, 10, 14, 8, tzinfo=TIMEZONE))
    submit(session, ana, challenge, False, datetime(2026, 10, 16, 8, tzinfo=TIMEZONE))

    assert SubmissionRepository(session).solve_days(ana.id) == {date(2026, 10, 14)}
