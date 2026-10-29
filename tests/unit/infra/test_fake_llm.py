import json

import pytest

from app.core.ports import LLMError
from app.domain.challenge_types import (
    ChallengeDraft,
    ChallengeType,
    assign_item_ids,
    challenge_errors,
    validate_challenge,
)
from app.domain.draft_rules import draft_rule_errors
from app.domain.hint_leak import hint_reveals_solution
from app.infra.llm.fake import FAKE_REVIEW, FakeLLMClient
from app.services.prompts import draft_prompt, hint_prompt, review_prompt
from tests.samples import CONTENT


def challenge(challenge_type: ChallengeType, statement: str) -> ChallengeDraft:
    return ChallengeDraft("Título", statement, challenge_type, CONTENT[challenge_type])


def saved_draft(challenge_type: ChallengeType, reply: dict) -> ChallengeDraft:
    content = assign_item_ids(challenge_type, reply["content"])
    return ChallengeDraft(
        reply["title"], reply["statement"], challenge_type, content, reply["explanation"]
    )


def ask(fake: FakeLLMClient, prompt) -> str:
    return fake.complete(prompt.system, prompt.user, max_tokens=200)


@pytest.mark.parametrize("challenge_type", list(ChallengeType))
@pytest.mark.parametrize("level", [1, 2, 3])
def test_T_AI_FAKE_01_default_hint_is_safe_and_names_the_level(challenge_type, level):
    fake = FakeLLMClient()
    prompt = hint_prompt(challenge(challenge_type, "Enunciado comum de teste."), level, [])

    hint = ask(fake, prompt)

    assert hint == f"Dica nível {level}: pense no que precisa acontecer primeiro. Qual seria?"
    assert not hint_reveals_solution(challenge_type, CONTENT[challenge_type], hint)


@pytest.mark.parametrize("challenge_type", list(ChallengeType))
def test_T_AI_FAKE_02_leak_trigger_returns_a_hint_that_reveals_the_solution(challenge_type):
    fake = FakeLLMClient()
    prompt = hint_prompt(challenge(challenge_type, "Enunciado [fake:leak] de teste."), 1, [])

    hint = ask(fake, prompt)

    assert hint_reveals_solution(challenge_type, CONTENT[challenge_type], hint)


def test_T_AI_FAKE_02b_error_trigger_makes_every_feature_fail():
    fake = FakeLLMClient()
    broken = challenge(ChallengeType.ORDERING, "Enunciado [fake:error] de teste.")

    with pytest.raises(LLMError):
        ask(fake, hint_prompt(broken, 1, []))
    with pytest.raises(LLMError):
        ask(fake, review_prompt(broken))


@pytest.mark.parametrize("challenge_type", list(ChallengeType))
def test_T_AI_FAKE_03_draft_is_valid_json_for_the_type_and_uses_the_topic(challenge_type):
    fake = FakeLLMClient()

    draft = json.loads(ask(fake, draft_prompt(challenge_type, "feira de ciências", [])))

    saved = saved_draft(challenge_type, draft)
    assert challenge_errors(saved) == []
    assert draft_rule_errors(saved) == []
    assert "feira de ciências" in draft["title"]
    assert "feira de ciências" in draft["statement"]


def test_T_AI_FAKE_03b_long_topic_still_gives_a_valid_title():
    fake = FakeLLMClient()

    draft = json.loads(ask(fake, draft_prompt(ChallengeType.PATTERN, "x" * 200, [])))

    assert validate_challenge(draft["title"], draft["statement"], draft["explanation"]) == []


def test_T_AI_FAKE_03d_easy_trigger_passes_the_template_but_breaks_the_draft_rules():
    fake = FakeLLMClient()

    reply = ask(fake, draft_prompt(ChallengeType.ORDERING, "tema [fake:easy]", []))

    saved = saved_draft(ChallengeType.ORDERING, json.loads(reply))
    assert challenge_errors(saved) == []
    assert draft_rule_errors(saved) != []


def test_T_AI_FAKE_03c_invalid_trigger_returns_text_that_is_not_json():
    fake = FakeLLMClient()

    reply = ask(fake, draft_prompt(ChallengeType.ORDERING, "tema [fake:invalid]", []))

    with pytest.raises(json.JSONDecodeError):
        json.loads(reply)


def test_T_AI_FAKE_04_review_text_and_prompts_appended_to_the_log(tmp_path):
    log = tmp_path / "fake-llm.jsonl"
    fake = FakeLLMClient(log_path=str(log))
    review = review_prompt(challenge(ChallengeType.FILTERING, "Enunciado comum de teste."))
    hint = hint_prompt(challenge(ChallengeType.PATTERN, "Enunciado comum de teste."), 2, [])

    assert ask(fake, review) == FAKE_REVIEW
    ask(fake, hint)

    lines = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert lines == [
        {"system": review.system, "user": review.user},
        {"system": hint.system, "user": hint.user},
    ]
