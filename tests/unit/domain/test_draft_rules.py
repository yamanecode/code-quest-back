import copy

import pytest

from app.domain.challenge_types import ChallengeDraft, ChallengeType, challenge_errors
from app.domain.draft_rules import draft_rule_errors, draft_rules
from tests.samples import CONTENT, DRAFT_CONTENT

STATEMENT = "Leia a situação com atenção e resolva o desafio proposto."


def draft(challenge_type: ChallengeType, content: dict, statement: str = STATEMENT):
    return ChallengeDraft("Desafio", statement, challenge_type, content)


def changed(challenge_type: ChallengeType, change) -> dict:
    content = copy.deepcopy(DRAFT_CONTENT[challenge_type])
    change(content)
    return content


@pytest.mark.parametrize("challenge_type", list(ChallengeType))
def test_T_DOM_DRAFT_01_sample_drafts_pass_the_template_and_draft_rules(challenge_type):
    sample = draft(challenge_type, DRAFT_CONTENT[challenge_type])

    assert challenge_errors(sample) == []
    assert draft_rule_errors(sample) == []


@pytest.mark.parametrize(
    ("challenge_type", "errors"),
    [
        (ChallengeType.ORDERING, ["Fácil demais: use pelo menos 5 passos."]),
        (
            ChallengeType.GROUPING,
            ["Fácil demais: use pelo menos 3 etapas.", "Fácil demais: use pelo menos 6 itens."],
        ),
        (
            ChallengeType.FILTERING,
            [
                "Fácil demais: use pelo menos 6 informações.",
                "Fácil demais: marque pelo menos 2 informações relevantes.",
            ],
        ),
        (ChallengeType.PATTERN, ["Fácil demais: mostre pelo menos 4 termos da sequência."]),
    ],
)
def test_T_DOM_DRAFT_02_small_challenges_are_too_easy(challenge_type, errors):
    # The small samples pass the template rules but are trivial for the audience.
    small = draft(challenge_type, CONTENT[challenge_type])
    assert challenge_errors(small) == []

    assert draft_rule_errors(small) == errors


def test_T_DOM_DRAFT_02_filtering_needs_two_irrelevant_items():
    content = changed(
        ChallengeType.FILTERING, lambda c: c.update(solution=["a", "b", "c", "d", "e"])
    )

    assert draft_rule_errors(draft(ChallengeType.FILTERING, content)) == [
        "Fácil demais: deixe pelo menos 2 informações irrelevantes."
    ]


def test_T_DOM_DRAFT_03_statement_must_not_give_the_answer():
    steps = [item["text"] for item in DRAFT_CONTENT[ChallengeType.ORDERING]["items"]]
    ordering = draft(
        ChallengeType.ORDERING, DRAFT_CONTENT[ChallengeType.ORDERING], ", ".join(steps)
    )
    question = "Some 10 minutos de caminhada e 25 minutos de ônibus: quanto tempo Lia leva?"
    filtering = draft(
        ChallengeType.FILTERING,
        changed(ChallengeType.FILTERING, lambda c: c.update(question=question)),
        "Lia caminha 10 minutos até o ponto e o ônibus leva 25 minutos até a escola.",
    )

    assert draft_rule_errors(ordering) == ["O enunciado entrega a resposta."]
    assert draft_rule_errors(filtering) == ["O enunciado entrega a resposta."]


@pytest.mark.parametrize(
    "text",
    [
        "Primeiro, lavar o arroz",
        "Depois refogar o arroz",
        "Em seguida acrescentar a água",
        "Por fim desligar o fogo",
        "Finalmente servir",
        "1. Lavar o arroz",
        "2) Refogar o arroz",
    ],
)
def test_T_DOM_DRAFT_04_steps_must_not_start_with_an_order_cue(text):
    content = changed(ChallengeType.ORDERING, lambda c: c["items"][0].update(text=text))

    assert draft_rule_errors(draft(ChallengeType.ORDERING, content)) == [
        "Nenhum passo pode começar com uma palavra ou número que indique a ordem "
        "(como “primeiro”, “depois”, “por fim” ou “1.”)."
    ]


def test_T_DOM_DRAFT_04_order_words_inside_a_step_are_allowed():
    text = "Esperar a água ferver antes de pôr o arroz"
    content = changed(ChallengeType.ORDERING, lambda c: c["items"][2].update(text=text))

    assert draft_rule_errors(draft(ChallengeType.ORDERING, content)) == []


def test_T_DOM_DRAFT_05_an_item_must_not_contain_its_own_group():
    text = "Escolher a alimentação dos convidados"
    content = changed(ChallengeType.GROUPING, lambda c: c["items"][0].update(text=text))

    assert draft_rule_errors(draft(ChallengeType.GROUPING, content)) == [
        "O item “Escolher a alimentação dos convidados” contém o nome da própria etapa "
        "(“Alimentação”)."
    ]


def test_T_DOM_DRAFT_05_another_groups_name_inside_an_item_is_allowed():
    # A word of another group misleads instead of helping, like a plausible distractor.
    text = "Divulgar o cardápio dos salgados"
    content = changed(ChallengeType.GROUPING, lambda c: c["items"][0].update(text=text))

    assert draft_rule_errors(draft(ChallengeType.GROUPING, content)) == []


@pytest.mark.parametrize(
    ("correct", "stands_out"),
    [
        ("33, porque cada termo é o dobro do anterior menos 1", True),
        ("33 pontos", True),
        ("1033", False),  # longer, but by fewer than 3 characters
    ],
)
def test_T_DOM_DRAFT_06_the_correct_option_must_not_stand_out_by_length(correct, stands_out):
    content = changed(ChallengeType.PATTERN, lambda c: c["options"][0].update(text=correct))
    expected = ["A opção correta é bem mais longa que as outras; deixe as opções parecidas."]

    result = draft_rule_errors(draft(ChallengeType.PATTERN, content))

    assert result == (expected if stands_out else [])


@pytest.mark.parametrize(
    ("sequence", "trivial"),
    [
        (["2", "4", "6", "8"], True),
        (["20", "17", "14", "11"], True),
        (["1,5", "2", "2,5", "3"], True),
        (["3", "5", "9", "17"], False),
        (["2", "4", "8", "16"], False),
        (["A", "B", "A", "B"], False),
        (["1", "2", "A", "4"], False),
    ],
)
def test_T_DOM_DRAFT_07_a_constant_step_number_sequence_is_too_easy(sequence, trivial):
    content = changed(ChallengeType.PATTERN, lambda c: c.update(sequence=sequence))
    expected = [
        "Fácil demais: a sequência soma sempre o mesmo valor. Use uma regra que peça mais "
        "raciocínio, como duas operações, alternância ou dependência da posição."
    ]

    assert draft_rule_errors(draft(ChallengeType.PATTERN, content)) == (expected if trivial else [])


@pytest.mark.parametrize("challenge_type", list(ChallengeType))
def test_T_DOM_DRAFT_08_rules_as_sentences_for_the_prompt(challenge_type):
    sentences = draft_rules(challenge_type)

    assert sentences
    assert all(sentence.endswith(".") for sentence in sentences)
    assert any("pelo menos" in sentence for sentence in sentences)
