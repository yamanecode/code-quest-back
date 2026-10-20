import pytest

from tests.functional.helpers import (
    Account,
    assert_error,
    challenge_payload,
    correct_answer,
    create_challenge,
    new_classroom,
    new_mission,
    request_hint,
    submit,
    turma_with_mission,
)

pytestmark = pytest.mark.functional


@pytest.mark.req("RF-02")
def test_FT_ACL_01_students_get_403_on_professor_endpoints(professor: Account, student: Account):
    turma = turma_with_mission(professor, ("pattern",))
    challenge_id = turma.challenges[0]["id"]
    calls = [
        ("GET", "/api/professor/classrooms", None),
        ("POST", "/api/professor/classrooms", {"name": "Turma de estudante"}),
        ("GET", f"/api/professor/classrooms/{turma.id}/progress", None),
        ("GET", f"/api/professor/classrooms/{turma.id}/rankings", None),
        ("GET", "/api/professor/challenges", None),
        ("POST", "/api/professor/challenges", challenge_payload("ordering")),
        ("GET", f"/api/professor/challenges/{challenge_id}", None),
        ("POST", f"/api/professor/challenges/{challenge_id}/ai-review", None),
        ("POST", "/api/professor/challenges/ai-draft", {"type": "pattern", "topic": "frutas"}),
        ("POST", f"/api/professor/missions/{turma.mission['id']}/unpublish", None),
    ]

    for method, path, body in calls:
        assert_error(student.client.request(method, path, json=body), 403)


@pytest.mark.req("RF-02")
def test_FT_ACL_02_professor_gets_404_on_another_professors_resources(
    professor: Account, other_professor: Account
):
    turma = turma_with_mission(professor, ("ordering",))
    classroom_id, mission_id = turma.id, turma.mission["id"]
    challenge = turma.challenges[0]
    challenge_id = challenge["id"]
    edit = {field: challenge[field] for field in ("title", "statement", "type", "content")}
    calls = [
        ("GET", f"/api/professor/classrooms/{classroom_id}", None),
        ("PUT", f"/api/professor/classrooms/{classroom_id}", {"name": "Tomada"}),
        ("GET", f"/api/professor/classrooms/{classroom_id}/missions", None),
        ("POST", f"/api/professor/classrooms/{classroom_id}/missions", {"title": "Intrusa"}),
        ("GET", f"/api/professor/classrooms/{classroom_id}/progress", None),
        ("GET", f"/api/professor/classrooms/{classroom_id}/rankings", None),
        ("GET", f"/api/professor/missions/{mission_id}", None),
        ("PUT", f"/api/professor/missions/{mission_id}", {"title": "Tomada", "position": 1}),
        ("PUT", f"/api/professor/missions/{mission_id}/challenges", {"challenge_ids": []}),
        ("POST", f"/api/professor/missions/{mission_id}/unpublish", None),
        ("DELETE", f"/api/professor/missions/{mission_id}", None),
        ("GET", f"/api/professor/challenges/{challenge_id}", None),
        ("PUT", f"/api/professor/challenges/{challenge_id}", edit | {"title": "Tomado"}),
        ("POST", f"/api/professor/challenges/{challenge_id}/duplicate", None),
        ("POST", f"/api/professor/challenges/{challenge_id}/unpublish", None),
        ("POST", f"/api/professor/challenges/{challenge_id}/ai-review", None),
        ("DELETE", f"/api/professor/challenges/{challenge_id}", None),
    ]

    for method, path, body in calls:
        assert_error(other_professor.client.request(method, path, json=body), 404)

    own = professor.client.get(f"/api/professor/classrooms/{classroom_id}").json()
    assert own["name"] == turma.classroom["name"]
    mission = professor.client.get(f"/api/professor/missions/{mission_id}").json()
    assert (mission["title"], mission["status"]) == (turma.mission["title"], "published")
    assert [c["id"] for c in mission["challenges"]] == [challenge_id]
    stored = professor.client.get(f"/api/professor/challenges/{challenge_id}").json()
    assert (stored["title"], stored["status"]) == (challenge["title"], "published")
    listed = other_professor.client.get("/api/professor/challenges").json()
    assert challenge_id not in [c["id"] for c in listed]
    classrooms = other_professor.client.get("/api/professor/classrooms").json()
    assert classroom_id not in [c["id"] for c in classrooms]


@pytest.mark.req("RF-02")
def test_FT_ACL_03_student_gets_404_on_classes_they_do_not_belong_to(
    professor: Account, student: Account
):
    turma = turma_with_mission(professor, ("filtering",))
    challenge = turma.challenges[0]
    loose = create_challenge(professor, "pattern")

    assert_error(student.client.get(f"/api/missions/{turma.mission['id']}"), 404)
    for target in (challenge, loose):
        answer = correct_answer(target["type"], target["content"])
        assert_error(student.client.get(f"/api/challenges/{target['id']}"), 404)
        assert_error(submit(student, target["id"], answer), 404)
        assert_error(request_hint(student, target["id"]), 404)
    ranking = student.client.get(
        "/api/rankings", params={"scope": "classroom", "classroom_id": turma.id, "period": "week"}
    )
    assert_error(ranking, 404)
    assert_error(student.client.delete(f"/api/classrooms/{turma.id}/membership"), 404)
    listing = student.client.get("/api/missions").json()
    assert listing["classrooms"] == []


@pytest.mark.req("RF-02")
def test_FT_ACL_04_another_professors_challenge_cannot_join_your_mission(
    professor: Account, other_professor: Account
):
    foreign = create_challenge(professor, "grouping")
    classroom = new_classroom(other_professor)
    own = create_challenge(other_professor, "pattern")
    mission = new_mission(other_professor, classroom["id"], [own["id"]])

    response = other_professor.client.put(
        f"/api/professor/missions/{mission['id']}/challenges",
        json={"challenge_ids": [own["id"], foreign["id"]]},
    )

    assert_error(response, 404)
    stored = other_professor.client.get(f"/api/professor/missions/{mission['id']}").json()
    assert [c["id"] for c in stored["challenges"]] == [own["id"]]
