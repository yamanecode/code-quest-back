import pytest

from tests.functional.helpers import (
    Account,
    assert_error,
    join,
    new_classroom,
    profile,
    solve,
    turma_with_mission,
)

pytestmark = pytest.mark.functional


def my_classroom_ids(student: Account) -> list[int]:
    response = student.client.get("/api/classrooms")
    assert response.status_code == 200, response.text
    return [classroom["id"] for classroom in response.json()]


@pytest.mark.req("RF-18")
def test_FT_CLASS_01_valid_code_adds_the_student(professor: Account, student: Account):
    classroom = new_classroom(professor)

    joined = join(student, classroom["join_code"])

    assert joined == {"id": classroom["id"], "name": classroom["name"]}
    assert my_classroom_ids(student) == [classroom["id"]]


@pytest.mark.req("RF-18")
def test_FT_CLASS_02_unknown_code_returns_404(student: Account):
    response = student.client.post("/api/classrooms/join", json={"join_code": "QQ00QQ"})

    assert_error(response, 404, "invalid_join_code")
    assert my_classroom_ids(student) == []


@pytest.mark.req("RF-18")
def test_FT_CLASS_03_joining_twice_changes_nothing(professor: Account, student: Account):
    classroom = new_classroom(professor)
    first = join(student, classroom["join_code"])

    second = join(student, classroom["join_code"])

    assert second == first
    assert my_classroom_ids(student) == [classroom["id"]]


@pytest.mark.req("RF-18")
def test_FT_CLASS_04_student_belongs_to_two_classes(professor: Account, student: Account):
    first = new_classroom(professor)
    second = new_classroom(professor)

    join(student, first["join_code"])
    join(student, second["join_code"])

    assert sorted(my_classroom_ids(student)) == sorted([first["id"], second["id"]])


@pytest.mark.req("RF-18")
def test_FT_CLASS_05_leaving_hides_missions_and_keeps_xp_and_badges(
    professor: Account, student: Account
):
    turma = turma_with_mission(professor, ("pattern",))
    challenge = turma.challenges[0]
    join(student, turma.join_code)
    solve(student, challenge)
    before = profile(student)

    response = student.client.delete(f"/api/classrooms/{turma.id}/membership")

    assert response.status_code == 204
    assert my_classroom_ids(student) == []
    assert_error(student.client.get(f"/api/missions/{turma.mission['id']}"), 404)
    assert_error(student.client.get(f"/api/challenges/{challenge['id']}"), 404)
    missions = student.client.get("/api/missions").json()
    assert all(classroom["id"] != turma.id for classroom in missions["classrooms"])
    after = profile(student)
    assert after["xp"] == before["xp"] == 10
    earned = {badge["code"] for badge in before["badges"] if badge["earned"]}
    assert {badge["code"] for badge in after["badges"] if badge["earned"]} == earned
    assert "first_solve" in earned
    assert_error(student.client.delete(f"/api/classrooms/{turma.id}/membership"), 404)
