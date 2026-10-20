from datetime import date, datetime, timedelta

import pytest

from app.core.clock import TIMEZONE
from app.domain.enums import ContentStatus
from app.infra.repositories.classrooms import ClassroomRepository
from tests.integration.factories import (
    NOON,
    add_member,
    first_solve,
    link,
    make_challenge,
    make_classroom,
    make_mission,
    make_user,
)

MONDAY = datetime(2026, 10, 12, tzinfo=TIMEZONE)
WEEK = MONDAY.date()


@pytest.fixture
def goal_turma(session):
    """Turma with two members, three goal challenges and some noise around them."""
    turma = make_classroom(session)
    ana, bia, outsider = make_user(session), make_user(session), make_user(session)
    add_member(session, ana, turma)
    add_member(session, bia, turma)
    mission = make_mission(session, turma)
    first, second, _third = (make_challenge(session, missions=(mission,)) for _ in range(3))
    link(session, make_mission(session, turma), first)  # same challenge in a second mission
    make_challenge(session, status=ContentStatus.DRAFT, missions=(mission,))
    in_draft_mission = make_challenge(
        session, missions=(make_mission(session, turma, status=ContentStatus.DRAFT),)
    )

    first_solve(session, ana, first, at=MONDAY)
    first_solve(session, ana, second, at=MONDAY - timedelta(days=1))
    first_solve(session, ana, in_draft_mission, at=MONDAY)
    first_solve(session, bia, first, at=MONDAY + timedelta(days=2))
    first_solve(session, outsider, second, at=MONDAY)
    return turma, ana, bia


def test_T_REPO_13_member_count(session):
    turma, other = make_classroom(session), make_classroom(session)
    for _ in range(2):
        add_member(session, make_user(session), turma)
    add_member(session, make_user(session), other)

    assert ClassroomRepository(session).member_count(turma.id) == 2


def test_T_REPO_14_goal_progress_counts_members_first_solves_this_week(session, goal_turma):
    turma, _, _ = goal_turma
    assert ClassroomRepository(session).goal_progress(turma.id, MONDAY) == 2


def test_T_REPO_15_goal_available_is_open_first_solves(session, goal_turma):
    turma, _, _ = goal_turma
    # 2 members x 3 published challenges - 1 first solve before Monday.
    assert ClassroomRepository(session).goal_available(turma.id, MONDAY) == 5


def test_T_REPO_16_goal_contributors(session, goal_turma):
    turma, ana, bia = goal_turma
    assert ClassroomRepository(session).goal_contributors(turma.id, MONDAY) == {ana.id, bia.id}


def test_T_REPO_17_goal_rewards_and_goals_contributed(session):
    turma, other = make_classroom(session), make_classroom(session)
    ana, bia = make_user(session), make_user(session)
    repo = ClassroomRepository(session)
    assert repo.has_goal_rewards(turma.id, WEEK) is False

    repo.add_goal_rewards(turma.id, WEEK, [ana.id, bia.id], created_at=NOON)
    repo.add_goal_rewards(turma.id, date(2026, 10, 19), [ana.id], created_at=NOON)
    repo.add_goal_rewards(other.id, WEEK, [ana.id], created_at=NOON)

    assert repo.has_goal_rewards(turma.id, WEEK) is True
    assert repo.goals_contributed(ana.id) == 3
    assert repo.goals_contributed(bia.id) == 1


def test_T_REPO_29_join_code_and_membership_round_trip(session):
    ana = make_user(session)
    turma = make_classroom(session)
    repo = ClassroomRepository(session)
    assert repo.get_by_join_code(turma.join_code) == turma

    membership = repo.add_member(ana.id, turma.id)
    assert repo.get_membership(ana.id, turma.id) == membership
    assert repo.member_classrooms(ana.id) == [turma]

    repo.remove_member(membership)
    assert repo.get_membership(ana.id, turma.id) is None
