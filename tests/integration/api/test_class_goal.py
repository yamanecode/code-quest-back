from datetime import timedelta

import pytest
from sqlalchemy import select

from app.domain.enums import ContentStatus, Role
from app.infra.db.models import ClassGoalReward
from tests.integration.auth_helpers import bearer
from tests.integration.factories import (
    NOON,
    add_member,
    first_solve,
    make_challenge,
    make_classroom,
    make_mission,
    make_user,
)
from tests.samples import CORRECT_ANSWER

pytestmark = pytest.mark.usefixtures("badge_catalog")

WEEK_START = "2026-10-12"  # Monday of NOON's week


def solve(client, clock, user, challenge):
    url = f"/api/challenges/{challenge.id}/submissions"
    payload = {"answer": CORRECT_ANSWER[challenge.type]}
    response = client.post(url, json=payload, headers=bearer(user, clock))
    assert response.status_code == 200
    return response.json()


def goal_of(client, clock, user, classroom):
    response = client.get("/api/classrooms", headers=bearer(user, clock))
    assert response.status_code == 200
    return next(item["goal"] for item in response.json() if item["id"] == classroom.id)


def earned(client, clock, user, code):
    badges = client.get("/api/me", headers=bearer(user, clock)).json()["badges"]
    return next(badge["earned"] for badge in badges if badge["code"] == code)


def turma_with(session, members, challenges, weekly_goal=None):
    turma = make_classroom(session, weekly_goal=weekly_goal)
    for member in members:
        add_member(session, member, turma)
    mission = make_mission(session, turma)
    return turma, [make_challenge(session, missions=(mission,)) for _ in range(challenges)]


def rewards(session, classroom):
    query = select(ClassGoalReward.user_id).where(ClassGoalReward.classroom_id == classroom.id)
    return sorted(session.scalars(query))


def test_T_STU_GOAL_01_progress_counts_members_first_solves_this_week(client, session, clock):
    ana, bia, outsider = (make_user(session, name) for name in ("ana", "bia", "fora"))
    turma, (old, first, second) = turma_with(session, [ana, bia], challenges=3)
    first_solve(session, ana, old, at=NOON - timedelta(days=7))
    base = make_challenge(session, missions=(make_mission(session),))

    solve(client, clock, ana, first)
    solve(client, clock, ana, first)  # a re-solve is not a first solve
    solve(client, clock, ana, base)  # base game challenges are not the turma's
    solve(client, clock, bia, second)
    first_solve(session, outsider, second)  # a former member: their history stays, uncounted

    # 2 members x 3 challenges - 1 solved before the week = 5 open first solves.
    assert goal_of(client, clock, ana, turma) == {
        "target": 5,
        "progress": 2,
        "week_start": WEEK_START,
        "completed": False,
    }


def test_T_STU_GOAL_02_reaching_the_target_rewards_every_contributor_once(client, session, clock):
    ana, bia, caio = (make_user(session, name) for name in ("ana", "bia", "caio"))
    turma, (first, second, third) = turma_with(session, [ana, bia, caio], 3, weekly_goal=2)

    assert "class_goal_1" not in {b["code"] for b in solve(client, clock, ana, first)["new_badges"]}
    reached = solve(client, clock, bia, second)

    assert "class_goal_1" in {badge["code"] for badge in reached["new_badges"]}
    assert earned(client, clock, ana, "class_goal_1")
    assert rewards(session, turma) == sorted([ana.id, bia.id])
    assert goal_of(client, clock, ana, turma)["completed"] is True

    after = solve(client, clock, ana, third)  # progress passes the target again
    assert "class_goal_1" not in {badge["code"] for badge in after["new_badges"]}
    assert rewards(session, turma) == sorted([ana.id, bia.id])


def test_T_STU_GOAL_03_members_who_did_not_contribute_get_nothing(client, session, clock):
    ana, caio = make_user(session, "ana"), make_user(session, "caio")
    turma, (first,) = turma_with(session, [ana, caio], challenges=1, weekly_goal=1)
    first_solve(session, caio, make_challenge(session, missions=(make_mission(session),)))

    solve(client, clock, ana, first)

    assert rewards(session, turma) == [ana.id]
    assert not earned(client, clock, caio, "class_goal_1")


def test_T_STU_GOAL_04_next_week_starts_at_zero(client, session, clock):
    ana = make_user(session, "ana")
    turma, (first, second, third) = turma_with(session, [ana], challenges=3, weekly_goal=1)
    solve(client, clock, ana, first)
    assert goal_of(client, clock, ana, turma)["completed"] is True

    clock.advance(timedelta(days=7))
    assert goal_of(client, clock, ana, turma) == {
        "target": 1,
        "progress": 0,
        "week_start": "2026-10-19",
        "completed": False,
    }
    solve(client, clock, ana, second)
    assert rewards(session, turma) == [ana.id, ana.id]  # one reward per week
    assert earned(client, clock, ana, "class_goal_1")


def test_T_STU_GOAL_05_professor_target_wins_over_the_automatic_one(client, session, clock):
    professor = make_user(session, "prof", role=Role.PROFESSOR)
    ana, bia = make_user(session, "ana"), make_user(session, "bia")
    turma = make_classroom(session, professor, weekly_goal=3)
    for member in (ana, bia):
        add_member(session, member, turma)
    mission = make_mission(session, turma)
    for _ in range(6):
        make_challenge(session, missions=(mission,))

    assert goal_of(client, clock, ana, turma)["target"] == 3

    headers = bearer(professor, clock)
    url = f"/api/professor/classrooms/{turma.id}"
    assert client.get(url, headers=headers).json()["goal"] == {
        "target": 3,
        "progress": 0,
        "week_start": WEEK_START,
        "completed": False,
    }
    client.put(url, json={"name": "Turma", "weekly_goal": None}, headers=headers)
    assert goal_of(client, clock, ana, turma)["target"] == 10  # max(10, 5 x 2 members)


def test_T_STU_GOAL_06_target_never_exceeds_the_open_first_solves(client, session, clock):
    ana = make_user(session, "ana")
    turma, _ = turma_with(session, [ana], challenges=2)
    big_goal, _ = turma_with(session, [ana], challenges=2, weekly_goal=50)

    assert goal_of(client, clock, ana, turma)["target"] == 2
    assert goal_of(client, clock, ana, big_goal)["target"] == 2


def test_T_STU_GOAL_07_no_goal_without_open_first_solves(client, session, clock):
    ana = make_user(session, "ana")
    empty = make_classroom(session)
    add_member(session, ana, empty)
    only_drafts = make_classroom(session)
    add_member(session, ana, only_drafts)
    make_challenge(
        session, status=ContentStatus.DRAFT, missions=(make_mission(session, only_drafts),)
    )
    all_done, (challenge,) = turma_with(session, [ana], challenges=1)
    first_solve(session, ana, challenge, at=NOON - timedelta(days=7))

    for turma in (empty, only_drafts, all_done):
        assert goal_of(client, clock, ana, turma) is None


def test_T_STU_GOAL_08_draft_challenge_never_completes_a_goal(client, session, clock):
    ana = make_user(session, "ana")
    turma, (published,) = turma_with(session, [ana], challenges=1, weekly_goal=1)
    hidden_mission = make_mission(session, turma, status=ContentStatus.DRAFT)
    other = make_challenge(session, missions=(hidden_mission, make_mission(session)))

    solve(client, clock, ana, other)  # visible through the base mission only

    assert rewards(session, turma) == []
    assert goal_of(client, clock, ana, turma)["progress"] == 0
    solve(client, clock, ana, published)
    assert rewards(session, turma) == [ana.id]
