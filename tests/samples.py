"""Valid sample content per challenge type, shared by unit and integration tests."""

from app.domain.challenge_types import ChallengeType

CONTENT = {
    ChallengeType.ORDERING: {
        "items": [
            {"id": "a", "text": "um"},
            {"id": "b", "text": "dois"},
            {"id": "c", "text": "três"},
        ],
        "solution": ["a", "b", "c"],
    },
    ChallengeType.GROUPING: {
        "groups": [{"id": "g1", "text": "Casa"}, {"id": "g2", "text": "Escola"}],
        "items": [
            {"id": "a", "text": "lavar"},
            {"id": "b", "text": "ler"},
            {"id": "c", "text": "varrer"},
            {"id": "d", "text": "estudar"},
        ],
        "solution": {"a": "g1", "b": "g2", "c": "g1", "d": "g2"},
    },
    ChallengeType.FILTERING: {
        "question": "Qual informação importa?",
        "items": [
            {"id": "a", "text": "preço"},
            {"id": "b", "text": "cor"},
            {"id": "c", "text": "peso"},
            {"id": "d", "text": "nome"},
        ],
        "solution": ["a"],
    },
    ChallengeType.PATTERN: {
        "sequence": ["2", "4", "8"],
        "options": [
            {"id": "a", "text": "16"},
            {"id": "b", "text": "10"},
            {"id": "c", "text": "12"},
            {"id": "d", "text": "14"},
        ],
        "solution": "a",
    },
}


CORRECT_ANSWER = {
    ChallengeType.ORDERING: {"order": ["a", "b", "c"]},
    ChallengeType.GROUPING: {"assignment": {"a": "g1", "b": "g2", "c": "g1", "d": "g2"}},
    ChallengeType.FILTERING: {"selected": ["a"]},
    ChallengeType.PATTERN: {"option": "a"},
}

WRONG_ANSWER = {
    ChallengeType.ORDERING: {"order": ["c", "b", "a"]},
    ChallengeType.GROUPING: {"assignment": {"a": "g1", "b": "g1", "c": "g1", "d": "g1"}},
    ChallengeType.FILTERING: {"selected": ["b"]},
    ChallengeType.PATTERN: {"option": "b"},
}
