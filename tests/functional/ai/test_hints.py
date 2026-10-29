import pytest

from tests.functional.helpers import (
    Account,
    LlmLog,
    appears_in_order,
    assert_error,
    item_texts,
    join,
    request_hint,
    send,
    solve,
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
def test_FT_AI_01_hint_levels_increase_and_hints_never_run_out(
    professor: Account, student: Account
):
    turma = turma_with_mission(professor, ("ordering",))
    challenge_id = turma.challenges[0]["id"]
    join(student, turma.join_code)

    hints = [hint_ok(student, challenge_id)]
    for _ in range(5):
        wait_cooldown(hints[-1]["cooldown_seconds"])
        hints.append(hint_ok(student, challenge_id))

    assert [hint["level"] for hint in hints] == [1, 2, 3, 3, 3, 3]
    assert "hints_left" not in challenge_view(student, challenge_id)


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

    wait_cooldown(body["retry_after"])
    assert hint_ok(student, challenge_id)["level"] == 2


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

    first = send(student, challenge, answer).json()
    view = challenge_view(student, challenge["id"])
    later = [send(student, challenge, answer).json() for _ in range(2)]
    prompts = llm_log.since(mark)

    assert first["is_correct"] is False
    assert isinstance(first["hint"], str) and first["hint"].strip()
    assert view["cooldown_seconds_left"] == 0
    assert [result["hint"] for result in later] == [None, None]
    assert len(prompts) == 1
    assert appears_in_order(prompts[0], [texts[item] for item in answer["order"]])

    assert hint_ok(student, challenge["id"])["level"] == 1
