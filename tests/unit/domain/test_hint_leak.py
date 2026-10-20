from app.domain.challenge_types import ChallengeType
from app.domain.hint_leak import hint_reveals_solution, normalize

ORDERING = {
    "items": [
        {"id": "a", "text": "Colocar o pão"},
        {"id": "b", "text": "Passar a manteiga"},
        {"id": "c", "text": "Pegar a faca"},
    ],
    "solution": ["c", "a", "b"],
}
GROUPING = {
    "groups": [{"id": "g1", "text": "Antes"}, {"id": "g2", "text": "Depois"}],
    "items": [
        {"id": "a", "text": "Comprar ingressos"},
        {"id": "b", "text": "Guardar a pipoca"},
    ],
    "solution": {"a": "g1", "b": "g2"},
}
FILTERING = {
    "question": "Quanto custa a viagem?",
    "items": [
        {"id": "a", "text": "Preço da passagem"},
        {"id": "b", "text": "Cor do ônibus"},
        {"id": "c", "text": "Taxa de embarque"},
    ],
    "solution": ["a", "c"],
}
PATTERN = {
    "sequence": ["2", "4", "8", "16"],
    "options": [{"id": "a", "text": "32"}, {"id": "b", "text": "24"}],
    "solution": "a",
}


def test_T_DOM_LEAK_01_ordering_hint_with_all_steps_in_solution_order_leaks():
    hint = "Primeiro pegar a faca, depois colocar o pão e por fim passar a manteiga."
    assert hint_reveals_solution(ChallengeType.ORDERING, ORDERING, hint)


def test_T_DOM_LEAK_02_ordering_hint_out_of_order_or_partial_is_safe():
    out_of_order = "Colocar o pão, pegar a faca e passar a manteiga."
    partial = "Antes de tudo, pegar a faca. Depois pense no resto."
    assert not hint_reveals_solution(ChallengeType.ORDERING, ORDERING, out_of_order)
    assert not hint_reveals_solution(ChallengeType.ORDERING, ORDERING, partial)


def test_T_DOM_LEAK_03_grouping_hint_with_every_item_leaks():
    hint = "Guardar a pipoca vem depois; comprar ingressos vem antes."
    assert hint_reveals_solution(ChallengeType.GROUPING, GROUPING, hint)


def test_T_DOM_LEAK_04_grouping_hint_missing_an_item_is_safe():
    hint = "Pense em quando dá para comprar ingressos."
    assert not hint_reveals_solution(ChallengeType.GROUPING, GROUPING, hint)


def test_T_DOM_LEAK_05_filtering_hint_with_every_relevant_item_leaks():
    leaking = "Use o preço da passagem e a taxa de embarque."
    safe = "O preço da passagem importa. E a cor do ônibus?"
    assert hint_reveals_solution(ChallengeType.FILTERING, FILTERING, leaking)
    assert not hint_reveals_solution(ChallengeType.FILTERING, FILTERING, safe)


def test_T_DOM_LEAK_06_pattern_hint_with_the_correct_option_leaks():
    assert hint_reveals_solution(ChallengeType.PATTERN, PATTERN, "A resposta é 32.")
    assert hint_reveals_solution(ChallengeType.PATTERN, PATTERN, "(32)")
    assert not hint_reveals_solution(ChallengeType.PATTERN, PATTERN, "Cada termo dobra. E agora?")


def test_T_DOM_LEAK_07_accents_case_and_spacing_are_ignored():
    assert normalize("  Preço   DA\nPassagem ") == "preco da passagem"
    hint = "PRECO DA PASSAGEM  e  taxa   de EMBARQUE."
    assert hint_reveals_solution(ChallengeType.FILTERING, FILTERING, hint)
    words = {**PATTERN, "options": [{"id": "a", "text": "Coração"}], "solution": "a"}
    assert hint_reveals_solution(ChallengeType.PATTERN, words, "Talvez CORACAO?")


def test_T_DOM_LEAK_08_pattern_option_must_be_a_whole_token():
    assert not hint_reveals_solution(ChallengeType.PATTERN, PATTERN, "Seria 320?")
    assert not hint_reveals_solution(ChallengeType.PATTERN, PATTERN, "Seria 132?")
    words = {**PATTERN, "options": [{"id": "a", "text": "par"}], "solution": "a"}
    assert not hint_reveals_solution(ChallengeType.PATTERN, words, "Compare os números.")
    assert hint_reveals_solution(ChallengeType.PATTERN, words, "É um número par.")
