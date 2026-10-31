from datetime import timedelta

from app.infra.repositories.submissions import SubmissionRepository
from app.infra.repositories.xp import XPRepository
from tests.integration.factories import NOON, make_challenge, make_user, submit


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


def test_T_REPO_23_last_answered_challenge_is_the_latest_submission(session):
    ana, bia = make_user(session), make_user(session)
    first, second = make_challenge(session), make_challenge(session)
    repo = SubmissionRepository(session)
    assert repo.last_answered_challenge_id(ana.id) is None

    submit(session, ana, second, False, NOON)
    submit(session, ana, first, False, NOON + timedelta(minutes=1))
    submit(session, bia, second, False, NOON + timedelta(minutes=2))

    assert repo.last_answered_challenge_id(ana.id) == first.id


def test_T_REPO_24_answered_challenges_include_wrong_answers(session):
    ana, bia = make_user(session), make_user(session)
    wrong, right, untouched = (make_challenge(session) for _ in range(3))
    submit(session, ana, wrong, False)
    submit(session, ana, right, True)
    submit(session, bia, untouched, False)

    assert SubmissionRepository(session).answered_challenge_ids(ana.id) == {wrong.id, right.id}


def test_T_REPO_25_persistent_solves_count_the_lowest_xp_grants(session):
    ana = make_user(session)
    xp = XPRepository(session)
    for amount in (10, 5, 2, 2):
        xp.add(ana.id, make_challenge(session).id, amount, created_at=NOON)

    assert xp.persistent_solves(ana.id) == 2
