"""Rules that keep AI drafts from being trivial for the audience (SG-14).

They apply only to AI drafts, after the template rules. Sources: the Bebras criteria for
good tasks (Dagienė and Futschek, 2008) and the multiple-choice item-writing guidelines of
Haladyna, Downing and Rodriguez (2002); "H" numbers below are their guideline numbers.
"""

import re
from collections.abc import Callable
from decimal import Decimal

from app.domain.challenge_types import ChallengeDraft, ChallengeType
from app.domain.hint_leak import hint_reveals_solution, normalize

# Not trivial in size (Bebras: a difficulty level adequate for the age; H2, H29).
MIN_ORDERING_STEPS = 5
MIN_GROUPS = 3
MIN_GROUPING_ITEMS = 6
MIN_FILTERING_ITEMS = 6
MIN_RELEVANT = 2
MIN_IRRELEVANT = 2
MIN_PATTERN_TERMS = 4

# A correct option stands out when it is this much longer than every distractor (H24, H28.4).
CONSPICUOUS_RATIO = 1.5
CONSPICUOUS_EXTRA_CHARS = 3

# Words that give away a step's place in the order by themselves (H28), already normalized.
ORDER_CUES = (
    "primeiro",
    "primeira",
    "segundo",
    "segunda",
    "terceiro",
    "terceira",
    "depois",
    "em seguida",
    "apos isso",
    "logo apos",
    "por fim",
    "por ultimo",
    "finalmente",
    "inicialmente",
    "no final",
    "para comecar",
    "para terminar",
)
_ORDER_CUE = re.compile(
    r"^(?:" + "|".join(re.escape(cue) for cue in ORDER_CUES) + r")\b|^\d+\s*[.)]"
)
_NUMBER = re.compile(r"-?\d+(?:[.,]\d+)?")

GIVES_ANSWER = "O enunciado entrega a resposta."
ORDER_CUE = (
    "Nenhum passo pode começar com uma palavra ou número que indique a ordem "
    "(como “primeiro”, “depois”, “por fim” ou “1.”)."
)
CONSPICUOUS = "A opção correta é bem mais longa que as outras; deixe as opções parecidas."
CONSTANT_STEP = (
    "Fácil demais: a sequência soma sempre o mesmo valor. Use uma regra que peça mais "
    "raciocínio, como duas operações, alternância ou dependência da posição."
)


def _at_least(count: int, minimum: int, message: str) -> list[str]:
    return [f"Fácil demais: {message.format(minimum)}"] if count < minimum else []


def _contains(text: str, part: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(normalize(part))}(?!\w)", normalize(text)) is not None


def _ordering(draft: ChallengeDraft) -> list[str]:
    items = draft.content["items"]
    errors = _at_least(len(items), MIN_ORDERING_STEPS, "use pelo menos {} passos.")
    if hint_reveals_solution(ChallengeType.ORDERING, draft.content, draft.statement):
        errors.append(GIVES_ANSWER)
    if any(_ORDER_CUE.search(normalize(item["text"])) for item in items):
        errors.append(ORDER_CUE)
    return errors


def _grouping(draft: ChallengeDraft) -> list[str]:
    groups = {group["id"]: group["text"] for group in draft.content["groups"]}
    items = draft.content["items"]
    errors = _at_least(len(groups), MIN_GROUPS, "use pelo menos {} etapas.")
    errors += _at_least(len(items), MIN_GROUPING_ITEMS, "use pelo menos {} itens.")
    # A clang association (H28.2): the item repeats the name of the group it belongs to.
    for item in items:
        group = groups[draft.content["solution"][item["id"]]]
        if _contains(item["text"], group):
            errors.append(f"O item “{item['text']}” contém o nome da própria etapa (“{group}”).")
    return errors


def _filtering(draft: ChallengeDraft) -> list[str]:
    items = draft.content["items"]
    relevant = len(draft.content["solution"])
    errors = _at_least(len(items), MIN_FILTERING_ITEMS, "use pelo menos {} informações.")
    errors += _at_least(relevant, MIN_RELEVANT, "marque pelo menos {} informações relevantes.")
    errors += _at_least(
        len(items) - relevant, MIN_IRRELEVANT, "deixe pelo menos {} informações irrelevantes."
    )
    stem = f"{draft.statement}\n{draft.content['question']}"
    if hint_reveals_solution(ChallengeType.FILTERING, draft.content, stem):
        errors.append(GIVES_ANSWER)
    return errors


def _constant_step(sequence: list[str]) -> bool:
    if not all(_NUMBER.fullmatch(term.strip()) for term in sequence):
        return False
    numbers = [Decimal(term.strip().replace(",", ".")) for term in sequence]
    steps = {after - before for before, after in zip(numbers, numbers[1:], strict=False)}
    return len(steps) == 1


def _pattern(draft: ChallengeDraft) -> list[str]:
    sequence = draft.content["sequence"]
    errors = _at_least(
        len(sequence), MIN_PATTERN_TERMS, "mostre pelo menos {} termos da sequência."
    )
    if _constant_step(sequence):
        errors.append(CONSTANT_STEP)
    options = {option["id"]: len(option["text"]) for option in draft.content["options"]}
    correct = options.pop(draft.content["solution"])
    longest = max(options.values())
    if correct > CONSPICUOUS_RATIO * longest and correct - longest >= CONSPICUOUS_EXTRA_CHARS:
        errors.append(CONSPICUOUS)
    return errors


_CHECKS: dict[str, Callable[[ChallengeDraft], list[str]]] = {
    ChallengeType.ORDERING: _ordering,
    ChallengeType.GROUPING: _grouping,
    ChallengeType.FILTERING: _filtering,
    ChallengeType.PATTERN: _pattern,
}


def draft_rule_errors(draft: ChallengeDraft) -> list[str]:
    """Every draft rule an AI draft breaks; the draft must already pass the template rules."""
    return _CHECKS[draft.type](draft)


_RULES = {
    ChallengeType.ORDERING: [
        f"Use pelo menos {MIN_ORDERING_STEPS} passos.",
        ORDER_CUE,
    ],
    ChallengeType.GROUPING: [
        f"Use pelo menos {MIN_GROUPS} etapas e {MIN_GROUPING_ITEMS} itens.",
        "Nenhum item pode conter o nome da própria etapa.",
    ],
    ChallengeType.FILTERING: [
        f"Use pelo menos {MIN_FILTERING_ITEMS} informações, com pelo menos {MIN_RELEVANT} "
        f"relevantes e {MIN_IRRELEVANT} irrelevantes.",
    ],
    ChallengeType.PATTERN: [
        f"Mostre pelo menos {MIN_PATTERN_TERMS} termos da sequência.",
        "A sequência não pode somar sempre o mesmo valor.",
        "A opção correta não pode ser bem mais longa que as outras.",
    ],
}


def draft_rules(challenge_type: str) -> list[str]:
    """The draft rules as PT-BR sentences, for the draft prompt."""
    return ["O enunciado não pode entregar a resposta.", *_RULES[challenge_type]]
