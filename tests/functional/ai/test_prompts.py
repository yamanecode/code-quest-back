import re
import unicodedata

import pytest

from tests.functional.helpers import (
    Account,
    LlmLog,
    appears_in_order,
    challenge_payload,
    create_challenge,
    item_texts,
    join,
    new_classroom,
    publish_mission,
    request_hint,
    submit,
    turma_with_mission,
    wait_cooldown,
    wrong_answer,
)

pytestmark = pytest.mark.functional

FAKE_HINT_LEVEL_1 = "Dica nível 1: pense no que precisa acontecer primeiro. Qual seria?"
NO_REVEAL = "nunca revele a solução"


def normalized(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def only_prompt(llm_log: LlmLog, mark: int) -> str:
    prompts = llm_log.since(mark)
    assert len(prompts) == 1, prompts
    return prompts[0]


def mentions_level(prompt: str, level: int) -> bool:
    return re.search(rf"n[ií]vel[^\n\d]{{0,30}}\b{level}\b", prompt, re.IGNORECASE) is not None


def holds_ordering_solution(prompt: str, content: dict) -> bool:
    """The solution is present as item texts in solution order or as the ordered list of ids."""
    texts = item_texts(content)
    solution = content["solution"]
    as_ids = r"\W{1,8}".join(rf"\b{re.escape(item)}\b" for item in solution)
    by_text = appears_in_order(prompt, [texts[item] for item in solution])
    return by_text or re.search(as_ids, prompt) is not None


def ordering_with_statement(professor: Account, marker: str) -> dict:
    payload = challenge_payload("ordering")
    payload["statement"] = f"{marker} {payload['statement']}"
    return create_challenge(professor, "ordering", payload=payload)


def leaks(hint: str, content: dict) -> bool:
    return all(normalized(text) in normalized(hint) for text in item_texts(content).values())


@pytest.mark.req("SG-01")
def test_FT_AI_10_hint_request_holds_statement_solution_level_and_instruction(
    professor: Account, new_student, llm_log: LlmLog
):
    turma = turma_with_mission(professor, ("ordering",))
    challenge = turma.challenges[0]
    content = challenge["content"]
    asking, failing = new_student(), new_student()
    join(asking, turma.join_code)
    join(failing, turma.join_code)

    mark = llm_log.mark()
    first = request_hint(asking, challenge["id"]).json()
    level_1 = only_prompt(llm_log, mark)
    wait_cooldown(first["cooldown_seconds"])
    mark = llm_log.mark()
    request_hint(asking, challenge["id"])
    level_2 = only_prompt(llm_log, mark)
    mark = llm_log.mark()
    submit(failing, challenge["id"], wrong_answer("ordering", content))
    after_wrong = only_prompt(llm_log, mark)

    for prompt, level in ((level_1, 1), (level_2, 2), (after_wrong, 1)):
        assert challenge["statement"] in prompt
        assert all(text in prompt for text in item_texts(content).values())
        assert holds_ordering_solution(prompt, content)
        assert mentions_level(prompt, level)
        assert normalized(NO_REVEAL) in normalized(prompt)
    assert first["hint"] in level_2


@pytest.mark.req("SG-03")
def test_FT_AI_11_hint_with_the_solution_is_replaced_by_the_fallback(
    professor: Account, student: Account, llm_log: LlmLog
):
    challenge = ordering_with_statement(professor, "[fake:leak]")
    classroom = new_classroom(professor)
    publish_mission(professor, classroom["id"], [challenge["id"]])
    join(student, classroom["join_code"])
    mark = llm_log.mark()

    response = request_hint(student, challenge["id"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert not leaks(body["hint"], challenge["content"])
    assert body["hint"] != FAKE_HINT_LEVEL_1
    assert (body["level"], body["hints_left"]) == (1, 4)
    assert len(llm_log.since(mark)) >= 2, "the leaking hint was not retried"
    view = student.client.get(f"/api/challenges/{challenge['id']}").json()
    assert view["hints_left"] == 4


@pytest.mark.req("SG-06")
def test_FT_AI_13_no_personal_data_reaches_the_ai(professor: Account, new_student, llm_log: LlmLog):
    turma = turma_with_mission(professor, ("ordering", "grouping"))
    hint_challenge, wrong_challenge = turma.challenges
    first, second = new_student(), new_student()
    join(first, turma.join_code)
    join(second, turma.join_code)
    private = [first.username, second.username, "ft_prof", turma.classroom["name"]]

    hint_prompts, wrong_prompts = [], []
    for student in (first, second):
        mark = llm_log.mark()
        assert request_hint(student, hint_challenge["id"]).status_code == 200
        hint_prompts.append(only_prompt(llm_log, mark))
        mark = llm_log.mark()
        answer = wrong_answer("grouping", wrong_challenge["content"])
        assert submit(student, wrong_challenge["id"], answer).status_code == 200
        wrong_prompts.append(only_prompt(llm_log, mark))
    mark = llm_log.mark()
    review = professor.client.post(f"/api/professor/challenges/{hint_challenge['id']}/ai-review")
    assert review.status_code == 200
    review_prompt = only_prompt(llm_log, mark)
    mark = llm_log.mark()
    draft = professor.client.post(
        "/api/professor/challenges/ai-draft",
        json={"type": "pattern", "topic": "números pares", "mission_id": turma.mission["id"]},
    )
    assert draft.status_code == 201
    draft_prompt = only_prompt(llm_log, mark)

    assert hint_prompts[0] == hint_prompts[1]
    assert wrong_prompts[0] == wrong_prompts[1]
    for prompt in hint_prompts + wrong_prompts + [review_prompt, draft_prompt]:
        for value in private:
            assert value not in prompt
        assert "user_id" not in prompt and "username" not in prompt


@pytest.mark.req("RNF-02")
def test_FT_AI_14_server_uses_the_provider_chosen_by_configuration(
    professor: Account, student: Account, llm_log: LlmLog
):
    turma = turma_with_mission(professor, ("filtering",))
    join(student, turma.join_code)
    mark = llm_log.mark()

    response = request_hint(student, turma.challenges[0]["id"])

    assert response.status_code == 200, response.text
    assert response.json()["hint"] == FAKE_HINT_LEVEL_1
    assert len(llm_log.since(mark)) == 1


@pytest.mark.req("RNF-03")
def test_FT_AI_15_application_keeps_working_when_the_ai_fails(professor: Account, student: Account):
    failing = ordering_with_statement(professor, "[fake:error]")
    leaking = ordering_with_statement(professor, "[fake:leak]")
    classroom = new_classroom(professor)
    publish_mission(professor, classroom["id"], [failing["id"], leaking["id"]])
    join(student, classroom["join_code"])

    on_failure = request_hint(student, failing["id"])
    on_leak = request_hint(student, leaking["id"])
    review = professor.client.post(f"/api/professor/challenges/{failing['id']}/ai-review")
    after_wrong = submit(student, failing["id"], wrong_answer("ordering", failing["content"]))

    assert on_failure.status_code == 200, on_failure.text
    fallback = on_failure.json()
    assert fallback["level"] == 1 and fallback["hint"].strip()
    assert fallback["hint"] != FAKE_HINT_LEVEL_1
    assert fallback["hint"] == on_leak.json()["hint"]
    assert review.status_code == 200, review.text
    assert review.json()["rule_violations"] == []
    assert isinstance(review.json()["suggestions"], str)
    assert after_wrong.status_code == 200, after_wrong.text
    assert after_wrong.json()["hint"].strip()
