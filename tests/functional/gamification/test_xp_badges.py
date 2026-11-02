import pytest

from tests.functional.helpers import (
    STUDENT_PASSWORD,
    TITLE_STEPS,
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

TITLES = {1: "Iniciante", 2: "Iniciante", 3: "Aprendiz", 4: "Aprendiz", 5: "Praticante"}
HIDDEN = {"all_types_day", "persistent", "explorer_base"}
NEEDS_CLASS = {
    "skill_ordering_15",
    "skill_grouping_15",
    "skill_filtering_15",
    "skill_pattern_15",
    "level_11",
    "mission_10",
    "first_try_30",
    "class_goal_1",
    "class_goal_5",
}


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
    turma = turma_with_mission(professor, ("pattern",) * 13)
    join(student, turma.join_code)
    start = profile(student)
    assert (start["xp"], start["level"], start["title"], start["xp_to_next_level"]) == (
        0,
        1,
        "Iniciante",
        30,
    )

    for count, challenge in enumerate(turma.challenges, start=1):
        result = solve(student, challenge)
        xp = 10 * count
        assert result["xp"] == xp
        assert result["level"] == xp // 30 + 1
        assert result["title"] == TITLES[result["level"]]
        assert result["level_up"] is (xp % 30 == 0)

    me = profile(student)
    assert (me["xp"], me["level"], me["title"], me["xp_to_next_level"]) == (
        130,
        5,
        "Praticante",
        20,
    )
    assert me["title_steps"] == TITLE_STEPS


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
    assert len(codes) == 26 == len(set(codes))
    for item in me["badges"]:
        assert item["tier"] in ("bronze", "silver", "gold")
        assert item["emoji"]
        assert item["earned"] is (item["earned_at"] is not None)
    assert {b["code"] for b in me["badges"] if b["requires_class"]} == NEEDS_CLASS
    assert all(badge["tier"] == "gold" for badge in me["badges"] if badge["hidden"])
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
        assert before[code]["requires_class"] is False
    assert all(not badge["hidden"] for code, badge in before.items() if code not in HIDDEN)

    turma = turma_with_mission(professor, ("grouping",))
    join(student, turma.join_code)
    for _ in range(3):
        fail(student, turma.challenges[0])
    result = solve(student, turma.challenges[0])

    assert "persistent" in [badge["code"] for badge in result["new_badges"]]
    after = badges_by_code(profile(student))["persistent"]
    assert after["earned"] is True
    assert after["name"] != "Insígnia secreta"
    assert after["description"]


@pytest.mark.req("SG-07")
def test_FT_GAME_17_login_continue_goal_badges_and_hints_add_no_xp(
    professor: Account, student: Account
):
    for _ in range(3):
        login(student.username, STUDENT_PASSWORD).client.close()
    assert student.client.get("/api/me/continue").status_code == 200
    turma = turma_with_mission(professor, ("ordering",), weekly_goal=1)
    join(student, turma.join_code)
    assert request_hint(student, turma.challenges[0]["id"]).status_code == 200
    assert profile(student)["xp"] == 0

    result = solve(student, turma.challenges[0])

    new_codes = {badge["code"] for badge in result["new_badges"]}
    assert {"first_solve", "mission_1", "class_goal_1"} <= new_codes
    assert result["xp_earned"] == 10
    assert student.client.get("/api/me/continue").status_code == 200
    assert profile(student)["xp"] == 10
