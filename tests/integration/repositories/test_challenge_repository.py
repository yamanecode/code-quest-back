from datetime import timedelta

from app.domain.challenge_types import ChallengeType
from app.domain.enums import ContentStatus, Role
from app.infra.repositories.challenges import ChallengeRepository, SolveStats
from tests.integration.factories import NOON, make_challenge, make_user, submit


def test_T_REPO_20_solve_stats_count_distinct_students(session):
    challenge = make_challenge(session)
    ana, bia, caio = make_user(session), make_user(session), make_user(session)
    submit(session, ana, challenge, correct=False)
    submit(session, ana, challenge, correct=True)
    submit(session, bia, challenge, correct=False)
    submit(session, bia, challenge, correct=False)
    submit(session, caio, challenge, correct=True)

    repo = ChallengeRepository(session)
    assert repo.solve_stats(challenge.id) == SolveStats(attempted=3, solved=2)
    assert repo.solve_stats(make_challenge(session).id) == SolveStats(attempted=0, solved=0)


def test_T_REPO_21_has_submissions(session):
    challenge = make_challenge(session)
    repo = ChallengeRepository(session)
    assert repo.has_submissions(challenge.id) is False

    submit(session, make_user(session), challenge, correct=False)
    assert repo.has_submissions(challenge.id) is True


def test_T_REPO_28_published_examples_newest_first_same_owner_and_type(session):
    professor = make_user(session, role=Role.PROFESSOR)
    repo = ChallengeRepository(session)
    examples = []
    for minutes in range(4):
        example = make_challenge(session, owner=professor)
        example.created_at = NOON + timedelta(minutes=minutes)
        examples.append(example)
    make_challenge(session, owner=professor, status=ContentStatus.DRAFT)
    make_challenge(session, owner=professor, challenge_type=ChallengeType.PATTERN)
    make_challenge(session)
    session.flush()

    found = repo.published_examples(professor.id, ChallengeType.ORDERING)
    assert found == [examples[3], examples[2], examples[1]]


def test_T_REPO_34_owned_ids_keeps_only_the_owners_challenges(session):
    owner, other = make_user(session, role=Role.PROFESSOR), make_user(session, role=Role.PROFESSOR)
    mine = make_challenge(session, owner)
    theirs = make_challenge(session, other)

    owned = ChallengeRepository(session).owned_ids(owner.id, [mine.id, theirs.id, 9999])

    assert owned == {mine.id}
