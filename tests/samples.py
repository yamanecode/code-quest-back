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

# Drafts that also pass the draft rules (SG-14): enough elements, no cues, plausible options.
DRAFT_CONTENT = {
    ChallengeType.ORDERING: {
        "items": [
            {"id": "a", "text": "Lavar o arroz em água corrente"},
            {"id": "b", "text": "Refogar o arroz lavado com alho"},
            {"id": "c", "text": "Acrescentar água fervente ao refogado"},
            {"id": "d", "text": "Cozinhar em fogo baixo até a água secar"},
            {"id": "e", "text": "Desligar o fogo e deixar a panela tampada"},
        ],
        "solution": ["a", "b", "c", "d", "e"],
    },
    ChallengeType.GROUPING: {
        "groups": [
            {"id": "g1", "text": "Alimentação"},
            {"id": "g2", "text": "Som e música"},
            {"id": "g3", "text": "Divulgação"},
        ],
        "items": [
            {"id": "a", "text": "Encomendar os salgados"},
            {"id": "b", "text": "Calcular quantos litros de suco comprar"},
            {"id": "c", "text": "Testar as caixas de som"},
            {"id": "d", "text": "Montar a lista de músicas"},
            {"id": "e", "text": "Criar o cartaz do evento"},
            {"id": "f", "text": "Enviar o convite no grupo da turma"},
        ],
        "solution": {"a": "g1", "b": "g1", "c": "g2", "d": "g2", "e": "g3", "f": "g3"},
    },
    ChallengeType.FILTERING: {
        "question": "Quanto tempo Lia leva de casa até a escola?",
        "items": [
            {"id": "a", "text": "Lia caminha 10 minutos até o ponto"},
            {"id": "b", "text": "Lia sai de casa às 6h40"},
            {"id": "c", "text": "O ônibus leva 25 minutos até a escola"},
            {"id": "d", "text": "O ônibus tem 40 lugares"},
            {"id": "e", "text": "A mochila de Lia pesa 4 kg"},
            {"id": "f", "text": "A escola tem 3 andares"},
        ],
        "solution": ["a", "c"],
    },
    ChallengeType.PATTERN: {
        "sequence": ["3", "5", "9", "17"],
        "options": [
            {"id": "a", "text": "33"},
            {"id": "b", "text": "25"},
            {"id": "c", "text": "34"},
            {"id": "d", "text": "31"},
        ],
        "solution": "a",
    },
}
