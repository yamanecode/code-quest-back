from app.domain.challenge_types import ChallengeType, is_text_list, student_ids


class InvalidAnswer(Exception):
    """The answer has the wrong shape or refers to ids the challenge does not have."""


ANSWER_KEYS = {
    ChallengeType.ORDERING: "order",
    ChallengeType.GROUPING: "assignment",
    ChallengeType.FILTERING: "selected",
    ChallengeType.PATTERN: "option",
}


def _answer_value(challenge_type: str, answer: object) -> object:
    key = ANSWER_KEYS.get(challenge_type)
    if key is None:
        raise InvalidAnswer(f"unknown challenge type {challenge_type!r}")
    if not isinstance(answer, dict) or set(answer) != {key}:
        raise InvalidAnswer(f"the answer must be an object with only the key {key!r}")
    return answer[key]


def _ids(content: dict, key: str) -> set[str]:
    return {element["id"] for element in content[key]}


def _stored_id(stored_by_shown: dict[str, str], shown: object) -> str:
    if not isinstance(shown, str) or shown not in stored_by_shown:
        raise InvalidAnswer("the answer uses an id the student was not shown")
    return stored_by_shown[shown]


def answer_from_student(challenge_type: str, content: dict, seed: str, answer: object) -> object:
    """The answer with the ids the student saw turned back into stored ids (SG-08).

    Wrong shapes are returned unchanged so that validate_answer reports them.
    """
    stored_by_shown = {
        shown: stored for stored, shown in student_ids(challenge_type, content, seed).items()
    }
    key = ANSWER_KEYS[challenge_type]
    if not stored_by_shown or not isinstance(answer, dict) or set(answer) != {key}:
        return answer
    value = answer[key]
    if challenge_type == ChallengeType.GROUPING and isinstance(value, dict):
        return {key: {_stored_id(stored_by_shown, item): group for item, group in value.items()}}
    if challenge_type != ChallengeType.GROUPING and isinstance(value, list):
        return {key: [_stored_id(stored_by_shown, item) for item in value]}
    return answer


def validate_answer(challenge_type: str, content: dict, answer: object) -> None:
    value = _answer_value(challenge_type, answer)
    if challenge_type == ChallengeType.ORDERING:
        if not is_text_list(value) or sorted(value) != sorted(_ids(content, "items")):
            raise InvalidAnswer("the order must list every item exactly once")
    elif challenge_type == ChallengeType.GROUPING:
        groups = _ids(content, "groups")
        if (
            not isinstance(value, dict)
            or set(value) != _ids(content, "items")
            or not all(isinstance(group, str) and group in groups for group in value.values())
        ):
            raise InvalidAnswer("every item must be assigned to an existing group")
    elif challenge_type == ChallengeType.FILTERING:
        if (
            not is_text_list(value)
            or len(set(value)) != len(value)
            or not set(value) <= _ids(content, "items")
        ):
            raise InvalidAnswer("the selection must list existing items without repeating")
    elif not isinstance(value, str) or value not in _ids(content, "options"):
        raise InvalidAnswer("the option must be one of the challenge's options")


def grade(challenge_type: str, content: dict, answer: dict) -> bool:
    validate_answer(challenge_type, content, answer)
    value = answer[ANSWER_KEYS[challenge_type]]
    if challenge_type == ChallengeType.FILTERING:
        return set(value) == set(content["solution"])
    return value == content["solution"]
