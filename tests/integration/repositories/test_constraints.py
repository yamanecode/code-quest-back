from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.enums import Role
from app.infra.repositories.daily import DailyRepository
from app.infra.repositories.users import UserRepository
from app.infra.repositories.xp import XPRepository
from tests.integration.factories import (
    NOON,
    add_member,
    make_challenge,
    make_classroom,
    make_user,
)


def _same_username(session):
    UserRepository(session).add("ana", "x", Role.STUDENT)
    UserRepository(session).add("ana", "y", Role.STUDENT)


def _same_membership(session):
    ana, turma = make_user(session), make_classroom(session)
    add_member(session, ana, turma)
    add_member(session, ana, turma)


def _second_first_solve(session):
    ana, challenge = make_user(session), make_challenge(session)
    XPRepository(session).add(ana.id, challenge.id, 10, created_at=NOON)
    XPRepository(session).add(ana.id, challenge.id, 5, created_at=NOON)


def _second_daily(session):
    ana = make_user(session)
    DailyRepository(session).add(ana.id, date(2026, 10, 14), make_challenge(session).id, NOON)
    DailyRepository(session).add(ana.id, date(2026, 10, 14), make_challenge(session).id, NOON)


def _goal_out_of_range(session):
    make_classroom(session, weekly_goal=1001)


@pytest.mark.parametrize(
    "violation",
    [_same_username, _same_membership, _second_first_solve, _second_daily, _goal_out_of_range],
)
def test_T_REPO_22_database_rejects_duplicates_and_bad_goals(session, violation):
    with pytest.raises(IntegrityError):
        violation(session)
    session.rollback()
