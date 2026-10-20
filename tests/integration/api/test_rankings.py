from datetime import datetime, timedelta

import pytest

from app.core.clock import TIMEZONE
from app.domain.enums import Role
from tests.integration.answers import as_student
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

MONDAY = datetime(2026, 10, 12, tzinfo=TIMEZONE)
FIRST_OF_MONTH = datetime(2026, 10, 1, tzinfo=TIMEZONE)


@pytest.fixture
def base_mission(session):
    return make_mission(session)


def earn(session, user, mission, amount, at=NOON):
    """One first solve worth `amount` XP on a new challenge of `mission`."""
    first_solve(session, user, make_challenge(session, missions=(mission,)), amount, at)


def ranking(client, clock, user, **params):
    response = client.get("/api/rankings", params=params, headers=bearer(user, clock))
    assert response.status_code == 200
    return response.json()


def rows(body):
    return [(entry["position"], entry["username"], entry["xp"]) for entry in body["entries"]]


def test_T_STU_RANK_01_weekly_counts_from_monday_midnight(client, session, clock, base_mission):
    ana, bia = make_user(session, "ana"), make_user(session, "bia")
    earn(session, ana, base_mission, 10)
    earn(session, ana, base_mission, 5, at=MONDAY - timedelta(minutes=1))  # last week
    earn(session, bia, base_mission, 5, at=MONDAY)

    body = ranking(client, clock, ana, scope="global", period="week")

    assert (body["scope"], body["period"]) == ("global", "week")
    assert rows(body) == [(1, "ana", 10), (2, "bia", 5)]


def test_T_STU_RANK_01_xp_earned_now_appears_in_both_periods(client, session, clock):
    ana = make_user(session, "ana")
    challenge = make_challenge(session, missions=(make_mission(session),))
    url = f"/api/challenges/{challenge.id}/submissions"
    headers = bearer(ana, clock)
    payload = {"answer": as_student(client, headers, challenge, CORRECT_ANSWER[challenge.type])}
    client.post(url, json=payload, headers=headers)

    for period in ("week", "month"):
        assert rows(ranking(client, clock, ana, period=period)) == [(1, "ana", 10)]


def test_T_STU_RANK_02_monthly_counts_from_day_one(client, session, clock, base_mission):
    ana, bia = make_user(session, "ana"), make_user(session, "bia")
    earn(session, ana, base_mission, 10, at=FIRST_OF_MONTH)
    earn(session, ana, base_mission, 5, at=MONDAY - timedelta(days=1))
    earn(session, bia, base_mission, 10, at=FIRST_OF_MONTH - timedelta(minutes=1))  # September

    body = ranking(client, clock, bia, scope="global", period="month")

    assert body["period"] == "month"
    assert rows(body) == [(1, "ana", 15), (2, "bia", 0)]


def test_T_STU_RANK_03_student_sees_self_plus_two_above_and_below(
    client, session, clock, base_mission
):
    students = [make_user(session, f"aluno{n}") for n in range(7)]
    for points, student in zip(range(70, 0, -10), students, strict=True):
        earn(session, student, base_mission, points)
    me = students[3]

    entries = ranking(client, clock, me)["entries"]

    assert [entry["username"] for entry in entries] == [f"aluno{n}" for n in range(1, 6)]
    assert [entry["is_me"] for entry in entries] == [False, False, True, False, False]
    assert entries[2] == {
        "position": 4,
        "username": "aluno3",
        "xp": 40,
        "is_me": True,
        "profile_public": False,
    }
    top = ranking(client, clock, students[0])["entries"]
    assert [entry["position"] for entry in top] == [1, 2, 3]


def test_T_STU_RANK_04_ties_share_the_position_and_are_listed_by_username(
    client, session, clock, base_mission
):
    carla, ana, bia = (make_user(session, name) for name in ("carla", "ana", "bia"))
    make_user(session, "dani", public=True)
    for student in (carla, ana):
        earn(session, student, base_mission, 10)
    earn(session, bia, base_mission, 5)

    body = ranking(client, clock, bia)  # third of four, so the window shows everyone

    assert rows(body) == [(1, "ana", 10), (1, "carla", 10), (2, "bia", 5), (3, "dani", 0)]
    assert body["entries"][-1]["profile_public"] is True


def test_T_STU_RANK_05_turma_scope_counts_only_that_turmas_challenges(
    client, session, clock, base_mission
):
    turma = make_classroom(session)
    ana, bia, outsider = (make_user(session, name) for name in ("ana", "bia", "fora"))
    for member in (ana, bia):
        add_member(session, member, turma)
    turma_mission = make_mission(session, turma)
    earn(session, ana, turma_mission, 5)
    earn(session, bia, base_mission, 10)  # base game XP doesn't count here
    earn(session, outsider, turma_mission, 10)  # not a member

    body = ranking(client, clock, bia, scope="classroom", classroom_id=turma.id)

    assert body["scope"] == "classroom"
    assert rows(body) == [(1, "ana", 5), (2, "bia", 0)]


def test_T_STU_RANK_06_global_counts_all_xp_of_every_student(client, session, clock, base_mission):
    turma = make_classroom(session)
    ana, bia = make_user(session, "ana"), make_user(session, "bia")
    add_member(session, ana, turma)
    make_user(session, "prof", role=Role.PROFESSOR)
    earn(session, ana, make_mission(session, turma), 5)
    earn(session, ana, base_mission, 10)

    assert rows(ranking(client, clock, bia, scope="global")) == [(1, "ana", 15), (2, "bia", 0)]


def test_T_STU_RANK_07_turma_ranking_needs_membership(client, session, clock):
    ana = make_user(session, "ana")
    other_turma = make_classroom(session)
    headers = bearer(ana, clock)

    params = {"scope": "classroom", "classroom_id": other_turma.id}
    response = client.get("/api/rankings", params=params, headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "classroom_not_found"
    missing = client.get("/api/rankings", params={"scope": "classroom"}, headers=headers)
    assert missing.status_code == 422
    for bad in ({"period": "year"}, {"scope": "everyone"}):
        assert client.get("/api/rankings", params=bad, headers=headers).status_code == 422


def test_T_PROF_RANK_01_professor_sees_the_full_turma_list(client, session, clock):
    professor = make_user(session, "prof", role=Role.PROFESSOR)
    turma = make_classroom(session, professor)
    students = [make_user(session, f"aluno{n}") for n in range(7)]
    mission = make_mission(session, turma)
    for points, student in zip(range(70, 0, -10), students, strict=True):
        add_member(session, student, turma)
        earn(session, student, mission, points)
    earn(session, students[6], mission, 55, at=FIRST_OF_MONTH)
    url = f"/api/professor/classrooms/{turma.id}/rankings"

    weekly = client.get(url, headers=bearer(professor, clock)).json()
    monthly = client.get(url, params={"period": "month"}, headers=bearer(professor, clock)).json()

    assert (weekly["scope"], weekly["period"]) == ("classroom", "week")
    assert len(weekly["entries"]) == 7
    assert not any(entry["is_me"] for entry in weekly["entries"])
    assert rows(monthly)[0] == (1, "aluno0", 70)
    assert rows(monthly)[1] == (2, "aluno6", 65)


def test_T_PROF_RANK_01_other_professors_turma_is_404(client, session, clock):
    turma = make_classroom(session)
    intruder = make_user(session, "intruso", role=Role.PROFESSOR)
    url = f"/api/professor/classrooms/{turma.id}/rankings"

    assert client.get(url, headers=bearer(intruder, clock)).status_code == 404
