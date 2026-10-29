import re
import unicodedata
from collections.abc import Callable

from app.domain.challenge_types import ChallengeType


def normalize(text: str) -> str:
    """Lower-case, without accents and with single spaces."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(without_accents.split())


def _texts_by_id(elements: list[dict]) -> dict[str, str]:
    return {element["id"]: normalize(element["text"]) for element in elements}


def _all_appear(texts: list[str], hint: str) -> bool:
    return all(text in hint for text in texts)


def _appear_in_order(texts: list[str], hint: str) -> bool:
    position = 0
    for text in texts:
        found = hint.find(text, position)
        if found == -1:
            return False
        position = found + len(text)
    return True


def _ordering_leaks(content: dict, hint: str) -> bool:
    texts = _texts_by_id(content["items"])
    return _appear_in_order([texts[item_id] for item_id in content["solution"]], hint)


def _grouping_leaks(content: dict, hint: str) -> bool:
    return _all_appear(list(_texts_by_id(content["items"]).values()), hint)


def _filtering_leaks(content: dict, hint: str) -> bool:
    texts = _texts_by_id(content["items"])
    return _all_appear([texts[item_id] for item_id in content["solution"]], hint)


def _pattern_leaks(content: dict, hint: str) -> bool:
    answer = _texts_by_id(content["options"])[content["solution"]]
    # Whole token only: the answer "32" must not match inside "320".
    return re.search(rf"(?<!\w){re.escape(answer)}(?!\w)", hint) is not None


_LEAK_RULES: dict[str, Callable[[dict, str], bool]] = {
    ChallengeType.ORDERING: _ordering_leaks,
    ChallengeType.GROUPING: _grouping_leaks,
    ChallengeType.FILTERING: _filtering_leaks,
    ChallengeType.PATTERN: _pattern_leaks,
}


def hint_reveals_solution(challenge_type: str, content: dict, hint: str) -> bool:
    """True when the hint contains the solution (SG-03); suggestions are not detected."""
    return _LEAK_RULES[challenge_type](content, normalize(hint))
