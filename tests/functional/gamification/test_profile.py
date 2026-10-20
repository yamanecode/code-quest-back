import pytest

from tests.functional.helpers import (
    Account,
    assert_error,
    base_challenge,
    correct_answer,
    join,
    profile,
    solve,
    submit,
    turma_with_mission,
    unique,
)

pytestmark = pytest.mark.functional


def daily(student: Account) -> dict:
    response = student.client.get("/api/daily-challenge")
    assert response.status_code == 200, response.text
    return response.json()


def visible_challenge_ids(student: Account) -> set[int]:
    listing = student.client.get("/api/missions").json()
    mission_ids = [m["id"] for m in listing["base"]] + [
        m["id"] for classroom in listing["classrooms"] for m in classroom["missions"]
    ]
    return {
        challenge["id"]
        for mission_id in mission_ids
        for challenge in student.client.get(f"/api/missions/{mission_id}").json()["challenges"]
    }


def set_public(student: Account, value: bool) -> None:
    response = student.client.put("/api/me/settings", json={"profile_public": value})
    assert response.status_code == 200, response.text
    assert response.json() == {"profile_public": value}


@pytest.mark.req("RF-10")
def test_FT_GAME_10_streak_starts_at_zero_and_counts_today(professor: Account, student: Account):
    assert profile(student)["streak"] == 0
    turma = turma_with_mission(professor, ("ordering", "pattern"))
    join(student, turma.join_code)

    solve(student, turma.challenges[0])
    solve(student, turma.challenges[1])

    me = profile(student)
    assert me["streak"] == 1
    assert me["xp"] == 20


@pytest.mark.req("RF-11")
def test_FT_GAME_11_daily_challenge_is_unsolved_visible_and_stable_today(student: Account):
    first = daily(student)

    assert first["all_solved"] is False
    challenge = first["challenge"]
    assert set(challenge) == {"id", "title", "type", "skill", "solved"}
    assert challenge["solved"] is False
    assert challenge["id"] in visible_challenge_ids(student)
    assert daily(student) == first

    view = student.client.get(f"/api/challenges/{challenge['id']}").json()
    source = base_challenge(view["title"], view["statement"])
    response = submit(student, challenge["id"], correct_answer(view["type"], source["content"]))
    assert response.json()["is_correct"] is True

    after = daily(student)
    assert after["all_solved"] is False
    assert after["challenge"] == challenge | {"solved": True}


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
