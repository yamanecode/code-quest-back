import pytest

from tests.functional.helpers import (
    Account,
    fail,
    join,
    monday_sao_paulo,
    my_goal,
    ranking,
    solve,
    turma_with_mission,
)

pytestmark = pytest.mark.functional

SCOPES_AND_PERIODS = [
    (scope, period) for scope in ("global", "classroom") for period in ("week", "month")
]


def my_entry(result: dict, student: Account) -> dict:
    mine = [entry for entry in result["entries"] if entry["is_me"]]
    assert len(mine) == 1, result
    assert mine[0]["username"] == student.username
    return mine[0]


@pytest.mark.req("RF-09")
@pytest.mark.req("SG-10")
def test_FT_GAME_06_student_sees_at_most_five_entries_including_themself(
    professor: Account, new_student
):
    turma = turma_with_mission(professor, ("pattern",))
    students = [new_student() for _ in range(7)]
    for student in students:
        join(student, turma.join_code)
    solve(students[3], turma.challenges[0])

    for student in students:
        for scope, period in SCOPES_AND_PERIODS:
            result = ranking(student, scope, period, turma.id if scope == "classroom" else None)
            assert (result["scope"], result["period"]) == (scope, period)
            assert 1 <= len(result["entries"]) <= 5
            my_entry(result, student)
            positions = [entry["position"] for entry in result["entries"]]
            assert positions == sorted(positions)
            for entry in result["entries"]:
                assert set(entry) == {"position", "username", "xp", "is_me", "profile_public"}


@pytest.mark.req("RF-09")
def test_FT_GAME_07_ties_share_the_position(professor: Account, new_student):
    turma = turma_with_mission(professor, ("pattern",))
    challenge = turma.challenges[0]
    alice, bruno, carla, davi = (new_student() for _ in range(4))
    for student in (alice, bruno, carla, davi):
        join(student, turma.join_code)
    solve(alice, challenge)
    solve(bruno, challenge)
    fail(carla, challenge)
    solve(carla, challenge)

    entries = ranking(carla, "classroom", "week", turma.id)["entries"]

    tied = sorted([alice.username, bruno.username])
    assert [(e["username"], e["xp"], e["position"]) for e in entries] == [
        (tied[0], 10, 1),
        (tied[1], 10, 1),
        (carla.username, 5, 2),
        (davi.username, 0, 3),
    ]


@pytest.mark.req("RF-09")
def test_FT_GAME_08_class_ranking_counts_only_that_class(professor: Account, student: Account):
    first = turma_with_mission(professor, ("ordering",))
    second = turma_with_mission(professor, ("grouping",))
    join(student, first.join_code)
    join(student, second.join_code)
    solve(student, first.challenges[0])
    fail(student, second.challenges[0])
    solve(student, second.challenges[0])

    for period in ("week", "month"):
        assert my_entry(ranking(student, "classroom", period, first.id), student)["xp"] == 10
        assert my_entry(ranking(student, "classroom", period, second.id), student)["xp"] == 5
        assert my_entry(ranking(student, "global", period), student)["xp"] == 15


@pytest.mark.req("SG-10")
def test_FT_GAME_09_xp_earned_now_counts_this_week_and_this_month(
    professor: Account, student: Account
):
    turma = turma_with_mission(professor, ("filtering",))
    join(student, turma.join_code)
    for scope, period in SCOPES_AND_PERIODS:
        result = ranking(student, scope, period, turma.id if scope == "classroom" else None)
        assert my_entry(result, student)["xp"] == 0

    solve(student, turma.challenges[0])

    for scope, period in SCOPES_AND_PERIODS:
        result = ranking(student, scope, period, turma.id if scope == "classroom" else None)
        assert my_entry(result, student)["xp"] == 10
    monday = monday_sao_paulo().isoformat()
    assert my_goal(student, turma.id)["week_start"] == monday
    professor_view = professor.client.get(f"/api/professor/classrooms/{turma.id}").json()
    assert professor_view["goal"]["week_start"] == monday
