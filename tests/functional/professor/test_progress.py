import pytest

from tests.functional.helpers import (
    Account,
    create_challenge,
    fail,
    join,
    new_classroom,
    publish_mission,
    ranking,
    request_hint,
    solve,
    turma_with_mission,
)

pytestmark = pytest.mark.functional


@pytest.mark.req("RF-16")
def test_FT_PROF_07_progress_matches_what_students_did(professor: Account, new_student):
    classroom = new_classroom(professor)
    first = [create_challenge(professor, "ordering"), create_challenge(professor, "pattern")]
    second = [create_challenge(professor, "filtering")]
    publish_mission(professor, classroom["id"], [c["id"] for c in first])
    publish_mission(professor, classroom["id"], [c["id"] for c in second])
    alice, bruno, carla = new_student(), new_student(), new_student()
    for student in (alice, bruno, carla):
        join(student, classroom["join_code"])

    assert request_hint(alice, first[1]["id"]).status_code == 200
    for challenge in first + second:
        solve(alice, challenge)
    fail(bruno, first[0])
    solve(bruno, first[0])

    response = professor.client.get(f"/api/professor/classrooms/{classroom['id']}/progress")

    assert response.status_code == 200, response.text
    body = response.json()
    rows = {row["username"]: row for row in body["students"]}
    assert set(rows) == {alice.username, bruno.username, carla.username}
    assert rows[alice.username] == {
        "username": alice.username,
        "xp_in_class": 30,
        "level": 1,
        "solved_in_class": 3,
        "missions_completed_in_class": 2,
        "hints_used": 1,
        "streak": 1,
    }
    assert rows[bruno.username] == {
        "username": bruno.username,
        "xp_in_class": 5,
        "level": 1,
        "solved_in_class": 1,
        "missions_completed_in_class": 0,
        "hints_used": 0,
        "streak": 1,
    }
    assert rows[carla.username] == {
        "username": carla.username,
        "xp_in_class": 0,
        "level": 1,
        "solved_in_class": 0,
        "missions_completed_in_class": 0,
        "hints_used": 0,
        "streak": 0,
    }
    assert body["completed_all_pct"] == 33


@pytest.mark.req("RF-16")
def test_FT_PROF_08_solve_stats_count_distinct_students(professor: Account, new_student):
    turma = turma_with_mission(professor, ("grouping",))
    challenge = turma.challenges[0]
    alice, bruno, carla = new_student(), new_student(), new_student()
    for student in (alice, bruno, carla):
        join(student, turma.join_code)

    fail(alice, challenge)
    solve(alice, challenge)
    fail(bruno, challenge)
    fail(bruno, challenge)

    listed = professor.client.get("/api/professor/challenges").json()
    stats = next(c for c in listed if c["id"] == challenge["id"])["solve_stats"]
    assert stats == {"attempted": 2, "solved": 1}
    detail = professor.client.get(f"/api/professor/challenges/{challenge['id']}").json()
    assert detail["solve_stats"] == {"attempted": 2, "solved": 1}


@pytest.mark.req("RF-16")
@pytest.mark.req("RF-09")
def test_FT_PROF_09_professor_ranking_lists_every_student(professor: Account, new_student):
    turma = turma_with_mission(professor, ("pattern", "filtering"))
    students = [new_student() for _ in range(6)]
    for student in students:
        join(student, turma.join_code)
    solve(students[0], turma.challenges[0])
    solve(students[0], turma.challenges[1])
    solve(students[1], turma.challenges[0])

    for period in ("week", "month"):
        response = professor.client.get(
            f"/api/professor/classrooms/{turma.id}/rankings", params={"period": period}
        )
        assert response.status_code == 200, response.text
        entries = response.json()["entries"]
        assert {entry["username"] for entry in entries} == {s.username for s in students}
        assert all(entry["is_me"] is False for entry in entries)
        xp = {entry["username"]: entry["xp"] for entry in entries}
        assert xp[students[0].username] == 20
        assert xp[students[1].username] == 10
        assert [entry["xp"] for entry in entries] == sorted(xp.values(), reverse=True)

    student_view = ranking(students[5], "classroom", "week", turma.id)["entries"]
    assert len(student_view) <= 5
