import copy

import pytest

from app.domain.challenge_types import (
    SKILL_DESCRIPTIONS,
    SKILL_LABELS,
    ChallengeType,
    assign_item_ids,
    structure_changed,
    template_rules,
    to_student_view,
    validate_challenge,
    validate_content,
)


def items(count: int) -> list[dict]:
    return [{"id": chr(ord("a") + i), "text": f"Passo {i + 1}"} for i in range(count)]


def ordering(count: int = 3) -> dict:
    content = {"items": items(count)}
    content["solution"] = [item["id"] for item in reversed(content["items"])]
    return content


def grouping(group_count: int = 2, item_count: int = 4) -> dict:
    groups = [{"id": f"g{i + 1}", "text": f"Etapa {i + 1}"} for i in range(group_count)]
    content = {"groups": groups, "items": items(item_count)}
    content["solution"] = {
        item["id"]: groups[i % group_count]["id"] for i, item in enumerate(content["items"])
    }
    return content


def filtering(item_count: int = 4, question: str = "Qual é a pergunta?") -> dict:
    return {"question": question, "items": items(item_count), "solution": ["a"]}


def pattern(terms: int = 3, option_count: int = 4) -> dict:
    return {
        "sequence": [str(2**i) for i in range(terms)],
        "options": [{"id": chr(ord("a") + i), "text": str(10 + i)} for i in range(option_count)],
        "solution": "a",
    }


def valid(challenge_type: ChallengeType, content: dict) -> bool:
    return validate_content(challenge_type, content) == []


def test_T_DOM_RULES_01_ordering_has_3_to_8_items():
    assert valid(ChallengeType.ORDERING, ordering(3))
    assert valid(ChallengeType.ORDERING, ordering(8))
    assert not valid(ChallengeType.ORDERING, ordering(2))
    assert not valid(ChallengeType.ORDERING, ordering(9))


def test_T_DOM_RULES_02_ordering_solution_is_a_permutation():
    for solution in (["a", "b"], ["a", "b", "b"], ["a", "b", "c", "d"], ["a", "b", "x"], "abc"):
        content = ordering(3)
        content["solution"] = solution
        assert not valid(ChallengeType.ORDERING, content), solution


def test_T_DOM_RULES_03_grouping_has_2_to_4_groups():
    assert valid(ChallengeType.GROUPING, grouping(2, 4))
    assert valid(ChallengeType.GROUPING, grouping(4, 4))
    assert not valid(ChallengeType.GROUPING, grouping(1, 4))
    assert not valid(ChallengeType.GROUPING, grouping(5, 5))


def test_T_DOM_RULES_04_grouping_has_4_to_10_items():
    assert valid(ChallengeType.GROUPING, grouping(2, 10))
    assert not valid(ChallengeType.GROUPING, grouping(2, 3))
    assert not valid(ChallengeType.GROUPING, grouping(2, 11))


def test_T_DOM_RULES_05_grouping_solution_assigns_every_item_and_uses_every_group():
    missing_item = grouping()
    del missing_item["solution"]["a"]
    unknown_group = grouping()
    unknown_group["solution"]["a"] = "g9"
    unused_group = grouping()
    unused_group["solution"] = {item_id: "g1" for item_id in unused_group["solution"]}
    not_a_dict = grouping()
    not_a_dict["solution"] = ["g1", "g2"]
    non_text_group = grouping()
    non_text_group["solution"]["a"] = 1

    for content in (missing_item, unknown_group, unused_group, not_a_dict, non_text_group):
        assert not valid(ChallengeType.GROUPING, content)


def test_T_DOM_RULES_06_filtering_question_has_10_to_200_chars():
    assert valid(ChallengeType.FILTERING, filtering(question="x" * 10))
    assert valid(ChallengeType.FILTERING, filtering(question="x" * 200))
    assert not valid(ChallengeType.FILTERING, filtering(question="x" * 9))
    assert not valid(ChallengeType.FILTERING, filtering(question="x" * 201))


def test_T_DOM_RULES_07_filtering_has_4_to_10_items():
    assert valid(ChallengeType.FILTERING, filtering(4))
    assert valid(ChallengeType.FILTERING, filtering(10))
    assert not valid(ChallengeType.FILTERING, filtering(3))
    assert not valid(ChallengeType.FILTERING, filtering(11))


def test_T_DOM_RULES_08_filtering_needs_relevant_and_irrelevant_items():
    for solution in ([], ["a", "b", "c", "d"], ["a", "a"], ["x"], "a"):
        content = filtering(4)
        content["solution"] = solution
        assert not valid(ChallengeType.FILTERING, content), solution
    content = filtering(4)
    content["solution"] = ["a", "b", "c"]
    assert valid(ChallengeType.FILTERING, content)


def test_T_DOM_RULES_09_pattern_sequence_has_3_to_8_terms_of_1_to_40_chars():
    assert valid(ChallengeType.PATTERN, pattern(terms=3))
    assert valid(ChallengeType.PATTERN, pattern(terms=8))
    assert not valid(ChallengeType.PATTERN, pattern(terms=2))
    assert not valid(ChallengeType.PATTERN, pattern(terms=9))

    long_term = pattern()
    long_term["sequence"][0] = "x" * 40
    assert valid(ChallengeType.PATTERN, long_term)
    for bad_term in ("x" * 41, "", 7):
        content = pattern()
        content["sequence"][0] = bad_term
        assert not valid(ChallengeType.PATTERN, content), bad_term


def test_T_DOM_RULES_10_pattern_has_4_to_5_options():
    assert valid(ChallengeType.PATTERN, pattern(option_count=4))
    assert valid(ChallengeType.PATTERN, pattern(option_count=5))
    assert not valid(ChallengeType.PATTERN, pattern(option_count=3))
    assert not valid(ChallengeType.PATTERN, pattern(option_count=6))


def test_T_DOM_RULES_11_pattern_solution_is_one_option_id():
    for solution in ("z", ["a"], None):
        content = pattern()
        content["solution"] = solution
        assert not valid(ChallengeType.PATTERN, content), solution


def test_T_DOM_RULES_12_texts_have_1_to_120_chars_unique_and_ids_unique():
    at_limit = ordering()
    at_limit["items"][0]["text"] = "x" * 120
    assert valid(ChallengeType.ORDERING, at_limit)

    for bad_text in ("x" * 121, "", "   ", None):
        content = ordering()
        content["items"][0]["text"] = bad_text
        assert not valid(ChallengeType.ORDERING, content), bad_text

    same_text = ordering()
    same_text["items"][1]["text"] = "  passo 1 "
    assert not valid(ChallengeType.ORDERING, same_text)

    group_equals_item = grouping()
    group_equals_item["groups"][0]["text"] = "Passo 1"
    assert not valid(ChallengeType.GROUPING, group_equals_item)

    repeated_id = ordering()
    repeated_id["items"][1]["id"] = "a"
    assert not valid(ChallengeType.ORDERING, repeated_id)

    for bad_id in ("", None, 3):
        content = pattern()
        content["options"][1]["id"] = bad_id
        assert not valid(ChallengeType.PATTERN, content), bad_id


def test_T_DOM_RULES_12_sequence_terms_may_repeat_or_equal_an_option():
    content = pattern()
    content["sequence"] = ["10", "10", "10"]
    assert valid(ChallengeType.PATTERN, content)


def test_T_DOM_RULES_13_challenge_title_statement_and_explanation_lengths():
    assert validate_challenge("x", "x" * 20, None) == []
    assert validate_challenge("x" * 80, "x" * 600, "x" * 400) == []
    assert validate_challenge("Título", "x" * 20, "") == []

    assert len(validate_challenge("", "x" * 20, None)) == 1
    assert len(validate_challenge("  ", "x" * 20, None)) == 1
    assert len(validate_challenge("x" * 81, "x" * 20, None)) == 1
    assert len(validate_challenge("x", "x" * 19, None)) == 1
    assert len(validate_challenge("x", "x" * 601, None)) == 1
    assert len(validate_challenge("x", "x" * 20, "x" * 401)) == 1
    assert len(validate_challenge(None, None, 5)) == 3


def test_T_DOM_RULES_14_malformed_content_and_unknown_type_give_messages():
    assert validate_content("drawing", ordering()) != []
    assert validate_content(ChallengeType.ORDERING, ["a", "b"]) != []
    assert validate_content(ChallengeType.ORDERING, {}) != []
    assert validate_content(ChallengeType.ORDERING, {"items": "abc", "solution": []}) != []
    assert validate_content(ChallengeType.ORDERING, {"items": ["a", "b", "c"]}) != []
    assert validate_content(ChallengeType.PATTERN, {"options": [], "sequence": "1 2 3"}) != []

    messages = validate_content(ChallengeType.ORDERING, ordering(2))
    assert all(isinstance(message, str) and message for message in messages)


def test_T_DOM_RULES_14_plain_strings_work_as_types():
    assert validate_content("ordering", ordering()) == []


def test_T_DOM_SKILL_01_labels_and_descriptions_follow_the_spec():
    assert SKILL_LABELS == {
        ChallengeType.ORDERING: "Pensamento algorítmico",
        ChallengeType.GROUPING: "Decomposição",
        ChallengeType.FILTERING: "Abstração",
        ChallengeType.PATTERN: "Reconhecimento de padrões",
    }
    assert SKILL_DESCRIPTIONS == {
        ChallengeType.ORDERING: (
            "Organizar a solução como uma sequência de passos em que a ordem importa."
        ),
        ChallengeType.GROUPING: (
            "Dividir um problema grande em partes menores, mais fáceis de resolver."
        ),
        ChallengeType.FILTERING: "Separar o que é essencial para o problema do que é detalhe.",
        ChallengeType.PATTERN: (
            "Encontrar a regra que se repete e usá-la para prever o próximo passo."
        ),
    }


def test_T_DOM_IDS_01_ids_become_canonical_and_solution_follows():
    draft = {
        "items": [{"id": "x1", "text": "A"}, {"id": "x2", "text": "B"}, {"id": "x3", "text": "C"}],
        "solution": ["x3", "x1", "x2"],
    }
    result = assign_item_ids(ChallengeType.ORDERING, draft)
    assert [item["id"] for item in result["items"]] == ["a", "b", "c"]
    assert result["solution"] == ["c", "a", "b"]
    assert draft["items"][0]["id"] == "x1"

    draft = {
        "groups": [{"id": "casa", "text": "Casa"}, {"id": "rua", "text": "Rua"}],
        "items": [{"id": "1", "text": "Varrer"}, {"id": "2", "text": "Atravessar"}],
        "solution": {"1": "casa", "2": "rua"},
    }
    result = assign_item_ids(ChallengeType.GROUPING, draft)
    assert [group["id"] for group in result["groups"]] == ["g1", "g2"]
    assert result["solution"] == {"a": "g1", "b": "g2"}

    draft = {
        "question": "Pergunta?",
        "items": [{"id": "p", "text": "A"}, {"id": "q", "text": "B"}],
        "solution": ["q"],
    }
    assert assign_item_ids(ChallengeType.FILTERING, draft)["solution"] == ["b"]

    draft = {
        "sequence": ["1", "2", "3"],
        "options": [{"id": "o1", "text": "4"}, {"id": "o2", "text": "5"}],
        "solution": "o2",
    }
    result = assign_item_ids(ChallengeType.PATTERN, draft)
    assert [option["id"] for option in result["options"]] == ["a", "b"]
    assert result["solution"] == "b"


def test_T_DOM_IDS_02_elements_without_id_get_one_by_position():
    draft = {"items": [{"text": "A"}, {"text": "B"}, {"id": "c", "text": "C"}], "solution": ["c"]}
    result = assign_item_ids(ChallengeType.ORDERING, draft)
    assert [item["id"] for item in result["items"]] == ["a", "b", "c"]

    many = {"items": [{"text": str(i)} for i in range(28)], "solution": []}
    ids = [item["id"] for item in assign_item_ids(ChallengeType.ORDERING, many)["items"]]
    assert ids[25:] == ["z", "i27", "i28"]
    assert len(set(ids)) == 28


def test_T_DOM_IDS_03_unknown_references_and_malformed_parts_stay_for_the_validator():
    draft = {
        "items": [{"id": "x", "text": "A"}, "not an element"],
        "solution": ["x", "ghost", 7],
    }
    result = assign_item_ids(ChallengeType.ORDERING, draft)
    assert result["solution"] == ["a", "ghost", 7]
    assert result["items"][1] == "not an element"

    assert assign_item_ids(ChallengeType.ORDERING, {"items": "abc"}) == {"items": "abc"}
    grouping_draft = {"groups": [], "items": [], "solution": "g1"}
    assert assign_item_ids(ChallengeType.GROUPING, grouping_draft)["solution"] == "g1"
    filtering_draft = {"items": [], "solution": "a"}
    assert assign_item_ids(ChallengeType.FILTERING, filtering_draft)["solution"] == "a"


def test_T_DOM_EDIT_01_text_only_edits_keep_the_structure():
    for challenge_type, content in (
        (ChallengeType.ORDERING, ordering()),
        (ChallengeType.GROUPING, grouping()),
        (ChallengeType.FILTERING, filtering()),
        (ChallengeType.PATTERN, pattern()),
    ):
        edited = copy.deepcopy(content)
        for key in ("items", "groups", "options"):
            for element in edited.get(key, []):
                element["text"] += " (novo)"
        if "question" in edited:
            edited["question"] = "Outra pergunta?"
        if "sequence" in edited:
            edited["sequence"] = ["3", "6", "9", "12"]
        assert not structure_changed(challenge_type, content, edited)


def test_T_DOM_EDIT_01_reordering_elements_or_filtering_solution_keeps_the_structure():
    content = filtering()
    content["solution"] = ["a", "c"]
    edited = copy.deepcopy(content)
    edited["items"].reverse()
    edited["solution"] = ["c", "a"]
    assert not structure_changed(ChallengeType.FILTERING, content, edited)


def test_T_DOM_EDIT_02_changing_an_id_changes_the_structure():
    content = pattern()
    edited = copy.deepcopy(content)
    edited["options"][3]["id"] = "z"
    assert structure_changed(ChallengeType.PATTERN, content, edited)


def test_T_DOM_EDIT_03_changing_a_count_changes_the_structure():
    content = grouping(2, 4)
    assert structure_changed(ChallengeType.GROUPING, content, grouping(3, 4))
    assert structure_changed(ChallengeType.GROUPING, content, grouping(2, 5))


def test_T_DOM_EDIT_04_changing_the_solution_changes_the_structure():
    content = ordering()
    edited = copy.deepcopy(content)
    edited["solution"] = ["a", "b", "c"]
    assert structure_changed(ChallengeType.ORDERING, content, edited)

    content = filtering()
    edited = copy.deepcopy(content)
    edited["solution"] = ["a", "b"]
    assert structure_changed(ChallengeType.FILTERING, content, edited)


def test_T_DOM_VIEW_01_student_view_has_skill_and_no_solution():
    for challenge_type, content in (
        (ChallengeType.ORDERING, ordering()),
        (ChallengeType.GROUPING, grouping()),
        (ChallengeType.FILTERING, filtering()),
        (ChallengeType.PATTERN, pattern()),
    ):
        view = to_student_view(challenge_type, content, "1:1")
        assert set(view) == {"type", "skill", "content"}
        assert view["type"] == challenge_type
        assert view["skill"] == SKILL_LABELS[challenge_type]
        assert "solution" not in view["content"]
        assert "explanation" not in view["content"]
        assert "solution" in content


def test_T_DOM_VIEW_02_ordering_shuffle_is_deterministic_per_seed():
    content = ordering(8)
    first = to_student_view(ChallengeType.ORDERING, content, "10:7")
    again = to_student_view(ChallengeType.ORDERING, content, "10:7")
    assert first == again

    orders = {
        tuple(item["id"] for item in to_student_view("ordering", content, seed)["content"]["items"])
        for seed in ("10:7", "10:8", "11:7")
    }
    assert len(orders) > 1


def test_T_DOM_VIEW_03_ordering_view_is_a_permutation_never_equal_to_the_solution():
    content = ordering(3)
    for user_id in range(200):
        view = to_student_view(ChallengeType.ORDERING, content, f"5:{user_id}")
        shown = [item["id"] for item in view["content"]["items"]]
        assert sorted(shown) == ["a", "b", "c"]
        assert shown != content["solution"]
        assert all(item in content["items"] for item in view["content"]["items"])


def test_T_DOM_VIEW_04_other_types_keep_the_stored_order_and_input_is_not_mutated():
    content = grouping()
    original = copy.deepcopy(content)
    view = to_student_view(ChallengeType.GROUPING, content, "1:2")
    assert view["content"] == {"groups": content["groups"], "items": content["items"]}

    view["content"]["items"][0]["text"] = "changed"
    assert content == original

    content = ordering()
    original = copy.deepcopy(content)
    to_student_view(ChallengeType.ORDERING, content, "1:2")
    assert content == original


def test_T_DOM_VIEW_04_unknown_type_is_rejected():
    with pytest.raises(ValueError):
        to_student_view("drawing", ordering(), "1:1")


@pytest.mark.parametrize(
    ("challenge_type", "expected"),
    [
        (ChallengeType.ORDERING, ["De 3 a 8 itens."]),
        (ChallengeType.GROUPING, ["De 2 a 4 etapas.", "De 4 a 10 itens."]),
        (
            ChallengeType.FILTERING,
            ["Pergunta com 10 a 200 caracteres.", "De 4 a 10 itens."],
        ),
        (
            ChallengeType.PATTERN,
            ["Sequência de 3 a 8 termos, cada um com 1 a 40 caracteres.", "De 4 a 5 opções."],
        ),
    ],
)
def test_T_DOM_RULES_15_template_rules_text_per_type(challenge_type, expected):
    rules = template_rules(challenge_type)

    assert set(expected) <= set(rules)
    assert "Título com 1 a 80 caracteres." in rules
    assert "Enunciado com 20 a 600 caracteres." in rules
    assert "Explicação opcional com no máximo 400 caracteres." in rules
    assert any("solução" in rule for rule in rules)
