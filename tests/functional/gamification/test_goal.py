import pytest

from tests.functional.helpers import (
    Account,
    create_challenge,
    fail,
    join,
    my_goal,
    new_classroom,
    new_mission,
    profile,
    solve,
    turma_with_mission,
)

pytestmark = pytest.mark.functional


def professor_goal(professor: Account, classroom_id: int) -> dict | None:
    response = professor.client.get(f"/api/professor/classrooms/{classroom_id}")
    assert response.status_code == 200, response.text
    return response.json()["goal"]


def earned(student: Account) -> list[str]:
    return [badge["code"] for badge in profile(student)["badges"] if badge["earned"]]


@pytest.mark.req("RF-19")
def test_FT_GAME_12_each_first_solve_of_a_member_adds_one(professor: Account, new_student):
    turma = turma_with_mission(professor, ("pattern", "filtering", "ordering"))
    first, second, _ = turma.challenges
    alice, bruno = new_student(), new_student()
    join(alice, turma.join_code)
    join(bruno, turma.join_code)
    assert my_goal(alice, turma.id) | {"week_start": None} == {
        "target": 6,
        "progress": 0,
        "completed": False,
        "week_start": None,
    }

    steps = [
        (lambda: solve(alice, first), 1),
        (lambda: solve(bruno, first), 2),
        (lambda: solve(alice, first), 2),
        (lambda: fail(alice, second), 2),
        (lambda: solve(alice, second), 3),
    ]
    for action, progress in steps:
        action()
        assert my_goal(alice, turma.id)["progress"] == progress
        assert my_goal(bruno, turma.id)["progress"] == progress
    assert professor_goal(professor, turma.id)["progress"] == 3


@pytest.mark.req("RF-19")
def test_FT_GAME_13_reaching_the_target_rewards_every_contributor_once(
    professor: Account, new_student
):
    turma = turma_with_mission(professor, ("pattern", "grouping"), weekly_goal=2)
    first, second = turma.challenges
    alice, bruno, carla = new_student(), new_student(), new_student()
    for student in (alice, bruno, carla):
        join(student, turma.join_code)

    solve(alice, first)
    assert my_goal(alice, turma.id)["completed"] is False
    assert "class_goal_1" not in earned(alice)
    result = solve(bruno, first)

    assert "class_goal_1" in [badge["code"] for badge in result["new_badges"]]
    goal = my_goal(carla, turma.id)
    assert (goal["target"], goal["progress"], goal["completed"]) == (2, 2, True)
    assert "class_goal_1" in earned(alice)
    assert "class_goal_1" in earned(bruno)
    assert "class_goal_1" not in earned(carla)

    later = solve(alice, second)
    assert "class_goal_1" not in [badge["code"] for badge in later["new_badges"]]
    assert my_goal(alice, turma.id)["progress"] == 3
    assert earned(alice).count("class_goal_1") == 1


@pytest.mark.req("RF-19")
def test_FT_GAME_14_professor_target_cap_and_no_goal(professor: Account, new_student):
    turma = turma_with_mission(professor, ("pattern",) * 4, weekly_goal=3)
    alice, bruno = new_student(), new_student()
    join(alice, turma.join_code)
    join(bruno, turma.join_code)
    assert my_goal(alice, turma.id)["target"] == 3

    response = professor.client.put(
        f"/api/professor/classrooms/{turma.id}",
        json={"name": turma.classroom["name"], "weekly_goal": None},
    )
    assert response.status_code == 200, response.text
    assert my_goal(alice, turma.id)["target"] == 8
    assert professor_goal(professor, turma.id)["target"] == 8

    small = turma_with_mission(professor, ("ordering", "grouping"), weekly_goal=50)
    join(alice, small.join_code)
    assert my_goal(alice, small.id)["target"] == 2
    professor.client.put(
        f"/api/professor/classrooms/{small.id}",
        json={"name": small.classroom["name"], "weekly_goal": None},
    )
    assert my_goal(alice, small.id)["target"] == 2

    empty = new_classroom(professor)
    drafts_only = new_classroom(professor)
    new_mission(professor, drafts_only["id"], [create_challenge(professor, "pattern")["id"]])
    for classroom in (empty, drafts_only):
        join(bruno, classroom["join_code"])
        assert my_goal(bruno, classroom["id"]) is None
        assert professor_goal(professor, classroom["id"]) is None
