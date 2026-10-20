import json

import pytest

from app.domain.challenge_types import ChallengeType, template_rules
from app.services.prompts import (
    LEVEL_INSTRUCTIONS,
    ChallengeText,
    draft_prompt,
    hint_prompt,
    review_prompt,
)
from tests.samples import CONTENT, WRONG_ANSWER

STATEMENT = "Coloque os passos na ordem certa para resolver o problema."


def challenge(challenge_type: ChallengeType) -> ChallengeText:
    return ChallengeText(
        type=challenge_type,
        title="Desafio de exemplo",
        statement=STATEMENT,
        content=CONTENT[challenge_type],
        explanation="Porque sim.",
    )


def element_texts(content: dict) -> list[str]:
    return [e["text"] for key in ("items", "groups", "options") for e in content.get(key, [])]


def full_text(prompt) -> str:
    return prompt.system + "\n" + prompt.user


# Solution as it must appear in the prompt: the texts, in the solution order where it matters.
SOLUTION_LINES = {
    ChallengeType.ORDERING: ["1. um", "2. dois", "3. três"],
    ChallengeType.GROUPING: ["lavar → Casa", "ler → Escola", "varrer → Casa", "estudar → Escola"],
    ChallengeType.FILTERING: ["Itens relevantes: preço"],
    ChallengeType.PATTERN: ["Resposta correta: 16"],
}


@pytest.mark.parametrize("challenge_type", list(ChallengeType))
def test_T_AI_PROMPT_01_hint_prompt_has_statement_items_solution_level_and_rules(challenge_type):
    prompt = hint_prompt(challenge(challenge_type), level=1, previous_hints=[])
    text = full_text(prompt)

    assert STATEMENT in prompt.user
    assert challenge_type.value in prompt.user
    for element in element_texts(CONTENT[challenge_type]):
        assert element in prompt.user
    for line in SOLUTION_LINES[challenge_type]:
        assert line in prompt.user
    assert "Nível da dica: 1" in prompt.user
    assert LEVEL_INSTRUCTIONS[1] in text
    assert "nunca revele a solução" in text
    assert "no máximo 3 frases" in text
    assert "termine com uma pergunta" in text


def test_T_AI_PROMPT_01b_each_level_has_its_own_instruction():
    for level in (1, 2, 3):
        prompt = hint_prompt(challenge(ChallengeType.ORDERING), level=level, previous_hints=[])
        assert f"Nível da dica: {level}" in prompt.user
        assert LEVEL_INSTRUCTIONS[level] in prompt.user
    assert "problema diferente" in LEVEL_INSTRUCTIONS[3]


ANSWER_TEXT = {
    ChallengeType.ORDERING: "Ordem enviada: três → dois → um",
    ChallengeType.GROUPING: "- estudar → Casa",
    ChallengeType.FILTERING: "Itens marcados: cor",
    ChallengeType.PATTERN: "Opção escolhida: 10",
}


@pytest.mark.parametrize("challenge_type", list(ChallengeType))
def test_T_AI_PROMPT_02_after_wrong_prompt_contains_the_answer_as_texts(challenge_type):
    prompt = hint_prompt(
        challenge(challenge_type),
        level=1,
        previous_hints=[],
        answer=WRONG_ANSWER[challenge_type],
    )

    assert "Resposta enviada pelo estudante" in prompt.user
    assert ANSWER_TEXT[challenge_type] in prompt.user


def test_T_AI_PROMPT_02b_empty_filtering_answer_is_rendered():
    prompt = hint_prompt(
        challenge(ChallengeType.FILTERING), level=1, previous_hints=[], answer={"selected": []}
    )

    assert "Itens marcados: nenhum item marcado" in prompt.user


def test_T_AI_PROMPT_02c_without_answer_there_is_no_answer_section():
    prompt = hint_prompt(challenge(ChallengeType.PATTERN), level=1, previous_hints=[])

    assert "Resposta enviada" not in prompt.user


def test_T_AI_PROMPT_04_previous_hints_are_listed():
    previous = ["Pense no começo.", "Qual passo vem antes de todos?"]

    prompt = hint_prompt(challenge(ChallengeType.ORDERING), level=2, previous_hints=previous)
    first = hint_prompt(challenge(ChallengeType.ORDERING), level=1, previous_hints=[])

    for hint in previous:
        assert hint in prompt.user
    assert "Dicas já mostradas: nenhuma." in first.user


def test_T_AI_PROMPT_04b_strict_retry_adds_a_warning():
    normal = hint_prompt(challenge(ChallengeType.ORDERING), level=1, previous_hints=[])
    strict = hint_prompt(challenge(ChallengeType.ORDERING), 1, [], strict=True)

    assert "foi descartada" in strict.user
    assert "foi descartada" not in normal.user


@pytest.mark.parametrize("challenge_type", list(ChallengeType))
def test_T_AI_PROMPT_05_review_prompt_has_challenge_with_solution_and_rules(challenge_type):
    prompt = review_prompt(challenge(challenge_type))

    assert STATEMENT in prompt.user
    assert "Desafio de exemplo" in prompt.user
    for element in element_texts(CONTENT[challenge_type]):
        assert element in prompt.user
    for line in SOLUTION_LINES[challenge_type]:
        assert line in prompt.user
    for rule in template_rules(challenge_type):
        assert rule in prompt.user


@pytest.mark.parametrize("challenge_type", list(ChallengeType))
def test_T_AI_PROMPT_05b_draft_prompt_has_type_topic_rules_schema_and_examples(challenge_type):
    example = challenge(challenge_type)

    prompt = draft_prompt(challenge_type, "receitas de bolo", [example])

    assert f"Tipo: {challenge_type.value}" in prompt.user
    assert "Tema: receitas de bolo" in prompt.user
    for rule in template_rules(challenge_type):
        assert rule in prompt.user
    assert '"solution"' in prompt.user
    assert json.dumps(example.content, ensure_ascii=False) in prompt.user
    assert "JSON" in prompt.system


def test_T_AI_PROMPT_05c_draft_prompt_without_examples_and_with_previous_errors():
    prompt = draft_prompt(
        ChallengeType.PATTERN, "estações do ano", [], errors=["Faltou a opção correta."]
    )

    assert "Exemplos" not in prompt.user
    assert "corrija" in prompt.user
    assert "- Faltou a opção correta." in prompt.user


@pytest.mark.parametrize("challenge_type", list(ChallengeType))
def test_T_AI_PROMPT_06_elements_are_listed_by_text_without_their_stored_ids(challenge_type):
    # Students see per-student ids, so a hint that named a stored id would point elsewhere.
    content = CONTENT[challenge_type]
    elements = [e for key in ("items", "groups", "options") for e in content.get(key, [])]
    prompts = [
        hint_prompt(challenge(challenge_type), 1, []),
        hint_prompt(challenge(challenge_type), 1, [], WRONG_ANSWER[challenge_type]),
        review_prompt(challenge(challenge_type)),
    ]

    for prompt in prompts:
        lines = prompt.user.splitlines()
        for element in elements:
            assert f"- {element['text']}" in lines
            assert f"- {element['id']}: {element['text']}" not in lines
