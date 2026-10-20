import pytest

from tests.functional.helpers import (
    Account,
    LlmLog,
    appears_in_order,
    assert_error,
    item_texts,
    join,
    request_hint,
    solve,
    submit,
    turma_with_mission,
    wait_cooldown,
    wrong_answer,
)

pytestmark = pytest.mark.functional


def challenge_view(student: Account, challenge_id: int) -> dict:
    response = student.client.get(f"/api/challenges/{challenge_id}")
    assert response.status_code == 200, response.text
    return response.json()


def hint_ok(student: Account, challenge_id: int) -> dict:
    response = request_hint(student, challenge_id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["hint"].strip()
    return body


@pytest.mark.req("RF-12")
def test_FT_AI_01_hint_levels_increase_and_hints_left_decreases(
    professor: Account, student: Account
):
    turma = turma_with_mission(professor, ("ordering",))
    challenge_id = turma.challenges[0]["id"]
    join(student, turma.join_code)
    assert challenge_view(student, challenge_id)["hints_left"] == 5

    hints = [hint_ok(student, challenge_id)]
    for _ in range(3):
        wait_cooldown(hints[-1]["cooldown_seconds"])
        hints.append(hint_ok(student, challenge_id))
    levels = [hint["level"] for hint in hints]
    left = [hint["hints_left"] for hint in hints]

    assert levels == [1, 2, 3, 3]
    assert left == [4, 3, 2, 1]
    assert challenge_view(student, challenge_id)["hints_left"] == 1


@pytest.mark.req("RF-12")
@pytest.mark.req("SG-04")
def test_FT_AI_02_request_before_the_wait_returns_429(professor: Account, student: Account):
    turma = turma_with_mission(professor, ("grouping",))
    challenge_id = turma.challenges[0]["id"]
    join(student, turma.join_code)
    first = hint_ok(student, challenge_id)

    early = request_hint(student, challenge_id)

    body = assert_error(early, 429, "hint_cooldown")
    assert isinstance(body["retry_after"], int)
    assert 1 <= body["retry_after"] <= first["cooldown_seconds"]
    assert early.headers["Retry-After"] == str(body["retry_after"])
    view = challenge_view(student, challenge_id)
    assert 1 <= view["cooldown_seconds_left"] <= first["cooldown_seconds"]
    assert view["hints_left"] == 4

    wait_cooldown(body["retry_after"])
    second = hint_ok(student, challenge_id)
    assert (second["level"], second["hints_left"]) == (2, 3)


@pytest.mark.req("RF-12")
@pytest.mark.req("SG-04")
def test_FT_AI_03_sixth_requested_hint_returns_409(professor: Account, student: Account):
    turma = turma_with_mission(professor, ("filtering",))
    challenge_id = turma.challenges[0]["id"]
    join(student, turma.join_code)
    for _ in range(5):
        body = hint_ok(student, challenge_id)
        wait_cooldown(body["cooldown_seconds"])
    assert body["hints_left"] == 0

    assert_error(request_hint(student, challenge_id), 409, "hint_cap_reached")
    assert challenge_view(student, challenge_id)["hints_left"] == 0


@pytest.mark.req("RF-12")
def test_FT_AI_04_solved_challenge_returns_409(professor: Account, student: Account):
    turma = turma_with_mission(professor, ("pattern",))
    join(student, turma.join_code)
    solve(student, turma.challenges[0])

    assert_error(request_hint(student, turma.challenges[0]["id"]), 409, "already_solved")


@pytest.mark.req("RF-13")
def test_FT_AI_05_first_wrong_answer_brings_one_automatic_hint(
    professor: Account, student: Account, llm_log: LlmLog
):
    turma = turma_with_mission(professor, ("ordering",))
    challenge = turma.challenges[0]
    join(student, turma.join_code)
    answer = wrong_answer("ordering", challenge["content"])
    texts = item_texts(challenge["content"])
    mark = llm_log.mark()

    first = submit(student, challenge["id"], answer).json()
    view = challenge_view(student, challenge["id"])
    later = [submit(student, challenge["id"], answer).json() for _ in range(2)]
    prompts = llm_log.since(mark)

    assert first["is_correct"] is False
    assert isinstance(first["hint"], str) and first["hint"].strip()
    assert (view["hints_left"], view["cooldown_seconds_left"]) == (5, 0)
    assert [result["hint"] for result in later] == [None, None]
    assert len(prompts) == 1
    assert appears_in_order(prompts[0], [texts[item] for item in answer["order"]])

    requested = hint_ok(student, challenge["id"])
    assert (requested["level"], requested["hints_left"]) == (1, 4)
