from datetime import date, datetime, timedelta

from app.core.clock import TIMEZONE
from app.domain.challenge_types import ChallengeType
from app.domain.enums import ContentStatus, Role
from app.infra.repositories.xp import XPRepository
from tests.integration.factories import (
    add_member,
    first_solve,
    make_challenge,
    make_classroom,
    make_mission,
    make_user,
    submit,
)

MONDAY = datetime(2026, 10, 12, tzinfo=TIMEZONE)


def _pairs(rows):
    return [(row.username, row.xp) for row in rows]


def test_T_REPO_01_xp_total_sums_only_the_user_events(session):
    ana, bia = make_user(session), make_user(session)
    first_solve(session, ana, make_challenge(session), amount=10)
    first_solve(session, ana, make_challenge(session), amount=5)
    first_solve(session, bia, make_challenge(session), amount=2)

    repo = XPRepository(session)
    assert repo.xp_total(ana.id) == 15
    assert repo.xp_total(make_user(session).id) == 0


def test_T_REPO_02_xp_by_user_since_starts_at_the_boundary(session):
    ana, bia = make_user(session, "ana"), make_user(session, "bia")
    make_user(session, "prof", role=Role.PROFESSOR)
    first_solve(session, ana, make_challenge(session), amount=10, at=MONDAY)
    first_solve(
        session, ana, make_challenge(session), amount=5, at=MONDAY - timedelta(microseconds=1)
    )

    repo = XPRepository(session)
    assert _pairs(repo.xp_by_user_since(MONDAY)) == [("ana", 10), ("bia", 0)]
    assert _pairs(repo.xp_by_user_since(MONDAY, user_ids=[bia.id])) == [("bia", 0)]


def test_T_REPO_03_xp_in_classroom_counts_members_on_turma_challenges(session):
    turma = make_classroom(session)
    ana, bia, outsider = make_user(session, "ana"), make_user(session, "bia"), make_user(session)
    add_member(session, ana, turma)
    add_member(session, bia, turma)
    published = make_mission(session, turma)
    draft = make_mission(session, turma, status=ContentStatus.DRAFT)
    in_turma = make_challenge(session, missions=(published, draft))
    older = make_challenge(session, missions=(published,))
    base = make_challenge(session, missions=(make_mission(session),))

    first_solve(session, ana, in_turma, amount=10, at=MONDAY)
    first_solve(session, ana, base, amount=5, at=MONDAY)
    first_solve(session, ana, older, amount=5, at=MONDAY - timedelta(days=1))
    first_solve(session, outsider, in_turma, amount=10, at=MONDAY)

    rows = XPRepository(session).xp_in_classroom_since(turma.id, MONDAY)
    assert _pairs(rows) == [("ana", 10), ("bia", 0)]


def test_T_REPO_08_first_solve_types_on_a_local_day(session):
    ana = make_user(session)
    day = date(2026, 10, 14)
    start = datetime(2026, 10, 14, tzinfo=TIMEZONE)
    first_solve(
        session, ana, make_challenge(session, challenge_type=ChallengeType.ORDERING), at=start
    )
    first_solve(
        session,
        ana,
        make_challenge(session, challenge_type=ChallengeType.PATTERN),
        at=start + timedelta(days=1, microseconds=-1),
    )
    first_solve(
        session,
        ana,
        make_challenge(session, challenge_type=ChallengeType.GROUPING),
        at=start + timedelta(days=1),
    )
    submit(
        session, ana, make_challenge(session, challenge_type=ChallengeType.FILTERING), True, start
    )

    assert XPRepository(session).first_solve_types_on(ana.id, day) == {"ordering", "pattern"}


def test_T_REPO_24_first_try_solves_count_events_of_10(session):
    ana = make_user(session)
    for amount in (10, 5, 10, 2):
        first_solve(session, ana, make_challenge(session), amount=amount)

    assert XPRepository(session).first_try_solves(ana.id) == 2


def test_T_REPO_25_first_solves_by_type(session):
    ana = make_user(session)
    for challenge_type in (ChallengeType.ORDERING, ChallengeType.ORDERING, ChallengeType.PATTERN):
        first_solve(session, ana, make_challenge(session, challenge_type=challenge_type))

    assert XPRepository(session).first_solves_by_type(ana.id) == {"ordering": 2, "pattern": 1}


def test_T_REPO_39_xp_in_classroom_total_counts_every_week(session):
    turma = make_classroom(session)
    ana, bia = make_user(session, "ana"), make_user(session, "bia")
    add_member(session, ana, turma)
    add_member(session, bia, turma)
    mission = make_mission(session, turma)
    this_week, last_month = (make_challenge(session, missions=(mission,)) for _ in range(2))
    base = make_challenge(session, missions=(make_mission(session),))

    first_solve(session, ana, this_week, amount=10, at=MONDAY)
    first_solve(session, ana, last_month, amount=5, at=MONDAY - timedelta(days=40))
    first_solve(session, ana, base, amount=10, at=MONDAY)

    rows = XPRepository(session).xp_in_classroom_total(turma.id)
    assert _pairs(rows) == [("ana", 15), ("bia", 0)]
