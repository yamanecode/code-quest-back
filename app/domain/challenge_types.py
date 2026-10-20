import copy
import hashlib
import string
from collections import Counter
from collections.abc import Callable
from enum import StrEnum


class ChallengeType(StrEnum):
    ORDERING = "ordering"
    GROUPING = "grouping"
    FILTERING = "filtering"
    PATTERN = "pattern"


SKILL_LABELS = {
    ChallengeType.ORDERING: "Pensamento algorítmico",
    ChallengeType.GROUPING: "Decomposição",
    ChallengeType.FILTERING: "Abstração",
    ChallengeType.PATTERN: "Reconhecimento de padrões",
}

SKILL_DESCRIPTIONS = {
    ChallengeType.ORDERING: (
        "Organizar a solução como uma sequência de passos em que a ordem importa."
    ),
    ChallengeType.GROUPING: (
        "Dividir um problema grande em partes menores, mais fáceis de resolver."
    ),
    ChallengeType.FILTERING: "Separar o que é essencial para o problema do que é detalhe.",
    ChallengeType.PATTERN: "Encontrar a regra que se repete e usá-la para prever o próximo passo.",
}

TITLE_MAX = 80
STATEMENT_MIN = 20
STATEMENT_MAX = 600
EXPLANATION_MAX = 400
TEXT_MAX = 120
QUESTION_MIN = 10
QUESTION_MAX = 200
TERM_MAX = 40

# (key in content, plural noun, "of the" phrase) used in PT-BR messages.
ITEMS = ("items", "itens", "dos itens")
GROUPS = ("groups", "etapas", "das etapas")
OPTIONS = ("options", "opções", "das opções")


def _text_ok(value: object, low: int, high: int) -> bool:
    return isinstance(value, str) and value.strip() != "" and low <= len(value) <= high


def _is_text_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(entry, str) for entry in value)


def _ids(elements: list[dict]) -> list[str]:
    return [element["id"] for element in elements if isinstance(element.get("id"), str)]


def validate_challenge(title: object, statement: object, explanation: object) -> list[str]:
    errors = []
    if not _text_ok(title, 1, TITLE_MAX):
        errors.append(f"O título deve ter de 1 a {TITLE_MAX} caracteres.")
    if not _text_ok(statement, STATEMENT_MIN, STATEMENT_MAX):
        errors.append(f"O enunciado deve ter de {STATEMENT_MIN} a {STATEMENT_MAX} caracteres.")
    if explanation is not None and (
        not isinstance(explanation, str) or len(explanation) > EXPLANATION_MAX
    ):
        errors.append(f"A explicação deve ter no máximo {EXPLANATION_MAX} caracteres.")
    return errors


def _check_elements(
    content: dict, kind: tuple[str, str, str], low: int, high: int, errors: list[str]
) -> list[dict]:
    key, noun, of_noun = kind
    elements = content.get(key)
    if not isinstance(elements, list) or not all(isinstance(e, dict) for e in elements):
        errors.append(f"A lista {of_noun} está em formato inválido.")
        return []
    if not low <= len(elements) <= high:
        errors.append(f"O desafio precisa ter de {low} a {high} {noun}.")
    ids = _ids(elements)
    if len(ids) != len(elements) or "" in ids or len(set(ids)) != len(ids):
        errors.append(f"Os ids {of_noun} devem ser únicos e não vazios.")
    if not all(_text_ok(element.get("text"), 1, TEXT_MAX) for element in elements):
        errors.append(f"Os textos {of_noun} devem ter de 1 a {TEXT_MAX} caracteres.")
    return elements


def _check_unique_texts(elements: list[dict], errors: list[str]) -> None:
    texts = [e["text"].strip().casefold() for e in elements if isinstance(e.get("text"), str)]
    if len(set(texts)) != len(texts):
        errors.append("Cada texto deve ser diferente dos outros neste desafio.")


def _validate_ordering(content: dict) -> list[str]:
    errors: list[str] = []
    items = _check_elements(content, ITEMS, 3, 8, errors)
    _check_unique_texts(items, errors)
    solution = content.get("solution")
    if not _is_text_list(solution) or Counter(solution) != Counter(_ids(items)):
        errors.append("A solução deve ordenar todos os itens, cada um uma única vez.")
    return errors


def _validate_grouping(content: dict) -> list[str]:
    errors: list[str] = []
    groups = _check_elements(content, GROUPS, 2, 4, errors)
    items = _check_elements(content, ITEMS, 4, 10, errors)
    _check_unique_texts(groups + items, errors)
    solution = content.get("solution")
    group_ids = set(_ids(groups))
    if (
        not isinstance(solution, dict)
        or set(solution) != set(_ids(items))
        or not all(isinstance(group_id, str) for group_id in solution.values())
        or not set(solution.values()) <= group_ids
    ):
        errors.append("A solução deve colocar cada item em uma das etapas.")
    elif set(solution.values()) != group_ids:
        errors.append("Cada etapa precisa de pelo menos um item.")
    return errors


def _validate_filtering(content: dict) -> list[str]:
    errors: list[str] = []
    if not _text_ok(content.get("question"), QUESTION_MIN, QUESTION_MAX):
        errors.append(f"A pergunta deve ter de {QUESTION_MIN} a {QUESTION_MAX} caracteres.")
    items = _check_elements(content, ITEMS, 4, 10, errors)
    _check_unique_texts(items, errors)
    solution = content.get("solution")
    item_ids = set(_ids(items))
    if (
        not _is_text_list(solution)
        or len(set(solution)) != len(solution)
        or not set(solution) <= item_ids
    ):
        errors.append("A solução deve listar itens existentes, sem repetir.")
    elif not 1 <= len(solution) < len(item_ids):
        errors.append("Marque pelo menos um item relevante e deixe pelo menos um irrelevante.")
    return errors


def _validate_pattern(content: dict) -> list[str]:
    errors: list[str] = []
    sequence = content.get("sequence")
    if not isinstance(sequence, list) or not 3 <= len(sequence) <= 8:
        errors.append("A sequência deve ter de 3 a 8 termos.")
    elif not all(_text_ok(term, 1, TERM_MAX) for term in sequence):
        errors.append(f"Cada termo da sequência deve ter de 1 a {TERM_MAX} caracteres.")
    options = _check_elements(content, OPTIONS, 4, 5, errors)
    _check_unique_texts(options, errors)
    solution = content.get("solution")
    if not isinstance(solution, str) or solution not in _ids(options):
        errors.append("A solução deve ser o id de uma das opções.")
    return errors


_VALIDATORS: dict[str, Callable[[dict], list[str]]] = {
    ChallengeType.ORDERING: _validate_ordering,
    ChallengeType.GROUPING: _validate_grouping,
    ChallengeType.FILTERING: _validate_filtering,
    ChallengeType.PATTERN: _validate_pattern,
}


def validate_content(challenge_type: str, content: object) -> list[str]:
    validator = _VALIDATORS.get(challenge_type)
    if validator is None:
        return ["Tipo de desafio inválido."]
    if not isinstance(content, dict):
        return ["O conteúdo do desafio está em formato inválido."]
    return validator(content)


def _letter_id(position: int) -> str:
    if position < len(string.ascii_lowercase):
        return string.ascii_lowercase[position]
    return f"i{position + 1}"


def _group_id(position: int) -> str:
    return f"g{position + 1}"


def _rename(elements: object, make_id: Callable[[int], str]) -> dict[str, str]:
    """Give each element its canonical id and return the old -> new mapping."""
    mapping: dict[str, str] = {}
    if not isinstance(elements, list):
        return mapping
    for position, element in enumerate(elements):
        if not isinstance(element, dict):
            continue
        old_id = element.get("id")
        new_id = make_id(position)
        if isinstance(old_id, str):
            mapping.setdefault(old_id, new_id)
        element["id"] = new_id
    return mapping


def _mapped(mapping: dict[str, str], value: object) -> object:
    return mapping.get(value, value) if isinstance(value, str) else value


def assign_item_ids(challenge_type: str, content: dict) -> dict:
    """Rename ids to a, b, c... (items, options) and g1, g2... (groups); rewrite the solution.

    Unknown references are kept as they are so that validate_content reports them.
    """
    result = copy.deepcopy(content)
    items = _rename(result.get("items"), _letter_id)
    groups = _rename(result.get("groups"), _group_id)
    options = _rename(result.get("options"), _letter_id)
    if "solution" not in result:
        return result
    solution = result["solution"]
    if challenge_type in (ChallengeType.ORDERING, ChallengeType.FILTERING):
        if isinstance(solution, list):
            result["solution"] = [_mapped(items, entry) for entry in solution]
    elif challenge_type == ChallengeType.GROUPING:
        if isinstance(solution, dict):
            result["solution"] = {
                _mapped(items, item_id): _mapped(groups, group_id)
                for item_id, group_id in solution.items()
            }
    else:
        result["solution"] = _mapped(options, solution)
    return result


def _structure(challenge_type: str, content: dict) -> tuple:
    ids = tuple(sorted(_ids(content.get(key, []))) for key in ("items", "groups", "options"))
    solution = content.get("solution")
    if challenge_type == ChallengeType.FILTERING:
        solution = sorted(solution)
    return ids, solution


def structure_changed(challenge_type: str, old_content: dict, new_content: dict) -> bool:
    """True when ids, element counts or the solution differ; text changes are allowed."""
    return _structure(challenge_type, old_content) != _structure(challenge_type, new_content)


def _shuffled(items: list[dict], solution: list[str], seed: str) -> list[dict]:
    def sort_key(item: dict) -> str:
        return hashlib.sha256(f"{seed}:{item['id']}".encode()).hexdigest()

    shuffled = sorted(items, key=sort_key)
    if [item["id"] for item in shuffled] == solution:
        shuffled = shuffled[1:] + shuffled[:1]
    return shuffled


def to_student_view(challenge_type: str, content: dict, seed: str) -> dict:
    """Content without the solution; ordering items in a per-student shuffled order."""
    challenge_type = ChallengeType(challenge_type)
    view = copy.deepcopy({key: value for key, value in content.items() if key != "solution"})
    if challenge_type == ChallengeType.ORDERING:
        view["items"] = _shuffled(view["items"], content["solution"], seed)
    return {"type": challenge_type, "skill": SKILL_LABELS[challenge_type], "content": view}
