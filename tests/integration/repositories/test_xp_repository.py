from datetime import date, datetime, timedelta

from app.core.clock import TIMEZONE
from app.domain.challenge_types import ChallengeType
from app.domain.enums import Role
from app.infra.repositories.xp import XPRepository
from tests.integration.factories import (
    first_solve,
    make_challenge,
    make_user,
    submit,
)

MONDAY = datetime(2026, 10, 12, tzinfo=TIMEZONE)


def _pairs(rows):
    return [(row.username, row.xp) for row in rows]


def test_T_REPO_02_xp_by_user_since_starts_at_the_boundary(session):
    ana = make_user(session, "ana")
    make_user(session, "bia")
    make_user(session, "prof", role=Role.PROFESSOR)
    first_solve(session, ana, make_challenge(session), amount=10, at=MONDAY)
    first_solve(
        session, ana, make_challenge(session), amount=5, at=MONDAY - timedelta(microseconds=1)
    )

    repo = XPRepository(session)
    assert _pairs(repo.xp_by_user_since(MONDAY)) == [("ana", 10), ("bia", 0)]


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
