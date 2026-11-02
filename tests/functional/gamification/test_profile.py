import pytest

from tests.functional.helpers import (
    Account,
    assert_error,
    base_as_challenge,
    create_challenge,
    fail,
    join,
    new_classroom,
    profile,
    publish_mission,
    solve,
    turma_with_mission,
    unique,
)

pytestmark = pytest.mark.functional


def set_public(student: Account, value: bool) -> None:
    response = student.client.put("/api/me/settings", json={"profile_public": value})
    assert response.status_code == 200, response.text
    assert response.json() == {"profile_public": value}


def missions(student: Account) -> dict:
    response = student.client.get("/api/missions")
    assert response.status_code == 200, response.text
    return response.json()


def mission_challenges(student: Account, mission_id: int) -> list[dict]:
    response = student.client.get(f"/api/missions/{mission_id}")
    assert response.status_code == 200, response.text
    return response.json()["challenges"]


def class_mission(student: Account, classroom_id: int) -> dict:
    classroom = next(c for c in missions(student)["classrooms"] if c["id"] == classroom_id)
    return classroom["missions"][0]


def is_new(student: Account, challenge_id: int) -> bool:
    response = student.client.get(f"/api/challenges/{challenge_id}")
    assert response.status_code == 200, response.text
    return response.json()["is_new"]


def continue_card(student: Account) -> dict | None:
    response = student.client.get("/api/me/continue")
    if response.status_code == 204:
        return None
    assert response.status_code == 200, response.text
    return response.json()


def card(mission: dict, challenge: dict, new: bool) -> dict:
    return {
        "mission_id": mission["id"],
        "mission_title": mission["title"],
        "challenge_id": challenge["id"],
        "challenge_title": challenge["title"],
        "is_new": new,
    }


@pytest.mark.req("RF-10")
def test_FT_GAME_10_recent_class_content_is_new_until_answered(
    professor: Account, student: Account
):
    turma = turma_with_mission(professor, ("ordering", "pattern"))
    first, second = turma.challenges
    mission_id = turma.mission["id"]
    join(student, turma.join_code)

    summary = class_mission(student, turma.id)
    assert (summary["is_new"], summary["has_new_challenges"]) == (True, False)
    assert [c["is_new"] for c in mission_challenges(student, mission_id)] == [True, True]
    assert is_new(student, first["id"]) is True

    fail(student, first)

    assert is_new(student, first["id"]) is False
    assert is_new(student, second["id"]) is True
    assert [c["is_new"] for c in mission_challenges(student, mission_id)] == [False, True]
    assert class_mission(student, turma.id)["is_new"] is False

    solve(student, first)
    solve(student, second)
    assert class_mission(student, turma.id)["has_new_challenges"] is False
    added = create_challenge(professor, "filtering")
    response = professor.client.put(
        f"/api/professor/missions/{mission_id}/challenges",
        json={"challenge_ids": [first["id"], second["id"], added["id"]]},
    )
    assert response.status_code == 200, response.text

    summary = class_mission(student, turma.id)
    assert (summary["is_new"], summary["has_new_challenges"]) == (False, True)
    assert [c["is_new"] for c in mission_challenges(student, mission_id)] == [False, False, True]

    for mission in missions(student)["base"]:
        assert (mission["is_new"], mission["has_new_challenges"]) == (False, False)
        challenges = mission_challenges(student, mission["id"])
        assert not any(challenge["is_new"] for challenge in challenges)
    assert is_new(student, challenges[0]["id"]) is False


@pytest.mark.req("RF-11")
@pytest.mark.req("SG-07")
def test_FT_GAME_11_continue_card_points_to_the_next_unsolved_challenge(
    professor: Account, student: Account
):
    base = missions(student)["base"]
    first_base = mission_challenges(student, base[0]["id"])
    assert continue_card(student) == card(base[0], first_base[0], False)

    classroom = new_classroom(professor)
    older_challenges = [create_challenge(professor, t) for t in ("ordering", "pattern")]
    newer_challenges = [create_challenge(professor, t) for t in ("grouping", "filtering")]
    older = publish_mission(professor, classroom["id"], [c["id"] for c in older_challenges])
    newer = publish_mission(professor, classroom["id"], [c["id"] for c in newer_challenges])
    join(student, classroom["join_code"])
    assert continue_card(student) == card(newer, newer_challenges[0], True)

    second_base = mission_challenges(student, base[1]["id"])
    target = base_as_challenge(student, second_base[0]["id"])
    fail(student, target)
    assert continue_card(student) == card(base[1], second_base[0], False)

    solve(student, newer_challenges[0])
    assert continue_card(student) == card(newer, newer_challenges[1], True)
    solve(student, newer_challenges[1])
    assert continue_card(student) == card(older, older_challenges[0], True)
    for challenge in older_challenges:
        solve(student, challenge)
    assert continue_card(student) == card(base[0], first_base[0], False)

    for mission in base:
        for challenge in mission_challenges(student, mission["id"]):
            solve(student, base_as_challenge(student, challenge["id"]))
    xp = profile(student)["xp"]

    assert continue_card(student) is None
    assert continue_card(student) is None
    assert profile(student)["xp"] == xp


@pytest.mark.req("RF-20")
@pytest.mark.req("SG-13")
def test_FT_GAME_15_public_profile_is_off_by_default_and_opt_in(professor: Account, new_student):
    owner, visitor = new_student(), new_student()
    path = f"/api/players/{owner.username}"
    assert profile(owner)["profile_public"] is False
    assert_error(visitor.client.get(path), 404, "player_not_found")

    set_public(owner, True)

    assert profile(owner)["profile_public"] is True
    assert visitor.client.get(path).status_code == 200
    assert professor.client.get(path).status_code == 200
    set_public(owner, False)
    assert_error(visitor.client.get(path), 404, "player_not_found")
    assert_error(visitor.client.get(f"/api/players/{unique()}"), 404, "player_not_found")
    assert_error(visitor.client.get("/api/players/ft_prof"), 404, "player_not_found")


@pytest.mark.req("SG-13")
@pytest.mark.req("RF-20")
def test_FT_GAME_16_public_profile_has_exactly_the_minimal_fields(professor: Account, new_student):
    owner, visitor = new_student(), new_student()
    turma = turma_with_mission(professor, ("filtering",))
    join(owner, turma.join_code)
    solve(owner, turma.challenges[0])
    set_public(owner, True)
    me = profile(owner)

    public = visitor.client.get(f"/api/players/{owner.username}").json()

    assert set(public) == {"username", "level", "title", "badges"}
    assert (public["username"], public["level"], public["title"]) == (
        owner.username,
        me["level"],
        me["title"],
    )
    for badge in public["badges"]:
        assert set(badge) == {"code", "name", "tier", "emoji"}
    earned = {badge["code"] for badge in me["badges"] if badge["earned"]}
    assert {badge["code"] for badge in public["badges"]} == earned
    assert "first_solve" in earned
