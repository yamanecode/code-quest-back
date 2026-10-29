import pytest

from app.domain.challenge_types import ChallengeType, student_ids
from app.domain.grading import InvalidAnswer, answer_from_student, grade, validate_answer

ORDERING = {
    "items": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}, {"id": "c", "text": "C"}],
    "solution": ["c", "a", "b"],
}
GROUPING = {
    "groups": [{"id": "g1", "text": "Casa"}, {"id": "g2", "text": "Rua"}],
    "items": [{"id": "a", "text": "Varrer"}, {"id": "b", "text": "Atravessar"}],
    "solution": {"a": "g1", "b": "g2"},
}
FILTERING = {
    "question": "O que importa?",
    "items": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}, {"id": "c", "text": "C"}],
    "solution": ["a", "c"],
}
PATTERN = {
    "sequence": ["2", "4", "8"],
    "options": [{"id": "a", "text": "16"}, {"id": "b", "text": "10"}],
    "solution": "a",
}


CONTENT = {
    ChallengeType.ORDERING: ORDERING,
    ChallengeType.GROUPING: GROUPING,
    ChallengeType.FILTERING: FILTERING,
    ChallengeType.PATTERN: PATTERN,
}


@pytest.mark.parametrize(
    ("challenge_type", "answer", "correct"),
    [
        (ChallengeType.ORDERING, {"order": ["c", "a", "b"]}, True),
        (ChallengeType.ORDERING, {"order": ["a", "b", "c"]}, False),
        (ChallengeType.GROUPING, {"assignment": {"b": "g2", "a": "g1"}}, True),
        (ChallengeType.GROUPING, {"assignment": {"a": "g2", "b": "g2"}}, False),
        (ChallengeType.FILTERING, {"selected": ["c", "a"]}, True),  # any order
        (ChallengeType.FILTERING, {"selected": ["a"]}, False),
        (ChallengeType.FILTERING, {"selected": ["a", "b", "c"]}, False),
        (ChallengeType.FILTERING, {"selected": []}, False),
        (ChallengeType.PATTERN, {"option": "a"}, True),
        (ChallengeType.PATTERN, {"option": "b"}, False),
    ],
)
def test_T_DOM_GRADE_01_correct_only_when_the_answer_equals_the_solution(
    challenge_type, answer, correct
):
    assert grade(challenge_type, CONTENT[challenge_type], answer) is correct


@pytest.mark.parametrize(
    ("challenge_type", "content", "answer"),
    [
        (ChallengeType.ORDERING, ORDERING, ["c", "a", "b"]),
        (ChallengeType.ORDERING, ORDERING, {}),
        (ChallengeType.ORDERING, ORDERING, {"order": ["c", "a", "b"], "extra": 1}),
        (ChallengeType.ORDERING, ORDERING, {"order": "cab"}),
        (ChallengeType.ORDERING, ORDERING, {"order": ["c", "a"]}),
        (ChallengeType.ORDERING, ORDERING, {"order": ["c", "a", "a"]}),
        (ChallengeType.ORDERING, ORDERING, {"order": ["c", "a", "x"]}),
        (ChallengeType.ORDERING, ORDERING, {"order": ["c", "a", "b", "b"]}),
        (ChallengeType.GROUPING, GROUPING, {"assignment": ["g1", "g2"]}),
        (ChallengeType.GROUPING, GROUPING, {"assignment": {"a": "g1"}}),
        (ChallengeType.GROUPING, GROUPING, {"assignment": {"a": "g1", "b": "g9"}}),
        (ChallengeType.GROUPING, GROUPING, {"assignment": {"a": "g1", "b": "g2", "x": "g1"}}),
        (ChallengeType.GROUPING, GROUPING, {"assignment": {"a": "g1", "b": ["g2"]}}),
        (ChallengeType.FILTERING, FILTERING, {"selected": "a"}),
        (ChallengeType.FILTERING, FILTERING, {"selected": ["a", "a"]}),
        (ChallengeType.FILTERING, FILTERING, {"selected": ["a", "x"]}),
        (ChallengeType.FILTERING, FILTERING, {"selected": [1]}),
        (ChallengeType.PATTERN, PATTERN, {"option": "z"}),
        (ChallengeType.PATTERN, PATTERN, {"option": ["a"]}),
        (ChallengeType.PATTERN, PATTERN, {"choice": "a"}),
        ("drawing", PATTERN, {"option": "a"}),
    ],
)
def test_T_DOM_GRADE_02_malformed_answers_raise(challenge_type, content, answer):
    with pytest.raises(InvalidAnswer):
        validate_answer(challenge_type, content, answer)
    with pytest.raises(InvalidAnswer):
        grade(challenge_type, content, answer)


def test_T_DOM_GRADE_02_empty_filtering_selection_is_well_formed():
    validate_answer(ChallengeType.FILTERING, FILTERING, {"selected": []})


def to_shown(challenge_type: str, content: dict, seed: str, answer: dict) -> dict:
    """The stored-id answer rewritten with the ids this student sees."""
    ids = student_ids(challenge_type, content, seed)
    key, value = next(iter(answer.items()))
    if isinstance(value, dict):
        return {key: {ids[item]: group for item, group in value.items()}}
    return {key: [ids[item] for item in value]}


@pytest.mark.parametrize(
    ("challenge_type", "content", "correct"),
    [
        (ChallengeType.ORDERING, ORDERING, {"order": ["c", "a", "b"]}),
        (ChallengeType.GROUPING, GROUPING, {"assignment": {"a": "g1", "b": "g2"}}),
        (ChallengeType.FILTERING, FILTERING, {"selected": ["a", "c"]}),
    ],
)
def test_T_DOM_GRADE_03_student_ids_are_mapped_back_before_grading(
    challenge_type, content, correct
):
    for seed in ("1:1", "1:2", "7:3"):
        shown = to_shown(challenge_type, content, seed, correct)
        assert answer_from_student(challenge_type, content, seed, shown) == correct
        assert grade(
            challenge_type, content, answer_from_student(challenge_type, content, seed, shown)
        )


@pytest.mark.parametrize(
    ("challenge_type", "content", "answer"),
    [
        (ChallengeType.ORDERING, ORDERING, {"order": ["a", "b", "z"]}),
        (ChallengeType.ORDERING, ORDERING, {"order": ["a", "b", 3]}),
        (ChallengeType.GROUPING, GROUPING, {"assignment": {"a": "g1", "z": "g2"}}),
        (ChallengeType.FILTERING, FILTERING, {"selected": ["z"]}),
        (ChallengeType.FILTERING, FILTERING, {"selected": [None]}),
    ],
)
def test_T_DOM_GRADE_04_an_id_the_student_was_not_shown_is_malformed(
    challenge_type, content, answer
):
    with pytest.raises(InvalidAnswer):
        answer_from_student(challenge_type, content, "1:1", answer)


@pytest.mark.parametrize(
    ("challenge_type", "content", "answer"),
    [
        (ChallengeType.ORDERING, ORDERING, ["a"]),
        (ChallengeType.ORDERING, ORDERING, {"order": "abc"}),
        (ChallengeType.ORDERING, ORDERING, {"order": ["a"], "extra": 1}),
        (ChallengeType.GROUPING, GROUPING, {"assignment": ["g1"]}),
        (ChallengeType.FILTERING, FILTERING, {"option": "a"}),
        (ChallengeType.PATTERN, PATTERN, {"option": "a"}),
        (ChallengeType.PATTERN, PATTERN, {"option": "z"}),
    ],
)
def test_T_DOM_GRADE_05_wrong_shapes_and_pattern_answers_pass_through_unchanged(
    challenge_type, content, answer
):
    assert answer_from_student(challenge_type, content, "1:1", answer) == answer
