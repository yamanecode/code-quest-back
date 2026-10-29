import pytest

from tests.functional.helpers import (
    STUDENT_PASSWORD,
    Account,
    assert_error,
    correct_answer,
    fail,
    join,
    login,
    profile,
    request_hint,
    send,
    solve,
    turma_with_mission,
)

pytestmark = pytest.mark.functional

TITLES = {1: "Aprendiz", 2: "Aprendiz", 3: "Explorador(a)"}
HIDDEN = {"all_types_day", "no_hint_mission"}


def badges_by_code(me: dict) -> dict[str, dict]:
    return {badge["code"]: badge for badge in me["badges"]}


@pytest.mark.req("RF-07")
@pytest.mark.req("SG-07")
def test_FT_GAME_01_xp_depends_on_wrong_answers_before_the_first_solve(
    professor: Account, student: Account
):
    turma = turma_with_mission(professor, ("pattern",) * 5)
    join(student, turma.join_code)
    expected = []
    for challenge, wrong_answers in zip(turma.challenges, (0, 1, 2, 3, 5), strict=True):
        for _ in range(wrong_answers):
            assert fail(student, challenge)["xp_earned"] == 0
        expected.append(solve(student, challenge)["xp_earned"])

    assert expected == [10, 5, 5, 2, 2]
    assert profile(student)["xp"] == 24


@pytest.mark.req("RF-07")
@pytest.mark.req("SG-07")
def test_FT_GAME_02_wrong_answers_hints_and_solved_challenges_give_no_xp(
    professor: Account, student: Account
):
    turma = turma_with_mission(professor, ("ordering", "grouping"))
    first, second = turma.challenges
    join(student, turma.join_code)
    solve(student, first)

    again = send(student, first, correct_answer(first["type"], first["content"]))
    hint = request_hint(student, second["id"])
    wrong = fail(student, second)

    assert_error(again, 409, "already_solved")
    assert hint.status_code == 200
    assert wrong["xp_earned"] == 0
    assert wrong["xp"] == 10
    assert profile(student)["xp"] == 10


@pytest.mark.req("RF-07")
def test_FT_GAME_03_level_and_title_follow_xp(professor: Account, student: Account):
    turma = turma_with_mission(professor, ("pattern",) * 10)
    join(student, turma.join_code)
    start = profile(student)
    assert (start["xp"], start["level"], start["title"], start["xp_to_next_level"]) == (
        0,
        1,
        "Aprendiz",
        50,
    )

    for count, challenge in enumerate(turma.challenges, start=1):
        result = solve(student, challenge)
        xp = 10 * count
        assert result["xp"] == xp
        assert result["level"] == xp // 50 + 1
        assert result["title"] == TITLES[result["level"]]
        assert result["level_up"] is (xp in (50, 100))

    me = profile(student)
    assert (me["xp"], me["level"], me["title"], me["xp_to_next_level"]) == (
        100,
        3,
        "Explorador(a)",
        50,
    )


@pytest.mark.req("RF-08")
def test_FT_GAME_04_first_solve_badge_is_listed_once_with_xp_and_level(
    professor: Account, student: Account
):
    turma = turma_with_mission(professor, ("filtering", "pattern"))
    join(student, turma.join_code)

    first = solve(student, turma.challenges[0])
    second = solve(student, turma.challenges[1])

    new_codes = [badge["code"] for badge in first["new_badges"]]
    assert new_codes.count("first_solve") == 1
    badge = next(b for b in first["new_badges"] if b["code"] == "first_solve")
    assert set(badge) == {"code", "name", "description", "tier", "emoji"}
    assert badge["tier"] == "bronze" and badge["emoji"]
    assert "first_solve" not in [b["code"] for b in second["new_badges"]]
    assert {"xp", "level", "title"} <= set(first)

    me = profile(student)
    assert {"xp", "level", "title"} <= set(me)
    codes = [b["code"] for b in me["badges"]]
    assert len(codes) == 30 == len(set(codes))
    for item in me["badges"]:
        assert item["tier"] in ("bronze", "silver", "gold")
        assert item["emoji"]
        assert item["earned"] is (item["earned_at"] is not None)
    earned = badges_by_code(me)["first_solve"]
    assert earned["earned"] is True
    locked = badges_by_code(me)["skill_ordering_15"]
    assert locked["earned"] is False and locked["description"]


@pytest.mark.req("RF-08")
def test_FT_GAME_05_hidden_badges_stay_secret_until_earned(professor: Account, student: Account):
    before = badges_by_code(profile(student))
    for code in HIDDEN:
        assert before[code]["hidden"] is True
        assert before[code]["earned"] is False
        assert before[code]["name"] == "Insígnia secreta"
        assert before[code]["description"] == ""
    assert all(not badge["hidden"] for code, badge in before.items() if code not in HIDDEN)

    turma = turma_with_mission(professor, ("grouping",))
    join(student, turma.join_code)
    result = solve(student, turma.challenges[0])

    assert "no_hint_mission" in [badge["code"] for badge in result["new_badges"]]
    after = badges_by_code(profile(student))["no_hint_mission"]
    assert after["earned"] is True
    assert after["name"] != "Insígnia secreta"
    assert after["description"]


@pytest.mark.req("SG-07")
def test_FT_GAME_17_login_daily_goal_badges_and_hints_add_no_xp(
    professor: Account, student: Account
):
    for _ in range(3):
        login(student.username, STUDENT_PASSWORD).client.close()
    assert student.client.get("/api/daily-challenge").status_code == 200
    turma = turma_with_mission(professor, ("ordering",), weekly_goal=1)
    join(student, turma.join_code)
    assert request_hint(student, turma.challenges[0]["id"]).status_code == 200
    assert profile(student)["xp"] == 0

    result = solve(student, turma.challenges[0])

    new_codes = {badge["code"] for badge in result["new_badges"]}
    assert {"first_solve", "mission_1", "class_goal_1"} <= new_codes
    assert result["xp_earned"] == 10
    me = profile(student)
    assert me["xp"] == 10
    assert me["streak"] == 1
