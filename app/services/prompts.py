"""Prompt builders for the AI features (SG-01, SG-06).

They only receive challenge data (ChallengeDraft), never a user or a turma, so personal
data cannot reach a prompt.
"""

import json
from dataclasses import dataclass

from app.domain.challenge_types import (
    SKILL_DESCRIPTIONS,
    SKILL_LABELS,
    ChallengeDraft,
    ChallengeType,
    template_rules,
)
from app.domain.draft_rules import draft_rules


@dataclass(frozen=True)
class Prompt:
    system: str
    user: str


HINT_SYSTEM = (
    "Você é um tutor de pensamento computacional para estudantes. "
    "Escreva uma dica para o desafio abaixo: guie o raciocínio, nunca revele a solução, "
    "use no máximo 3 frases, escreva em português do Brasil e termine com uma pergunta."
)

LEVEL_INSTRUCTIONS = {
    1: (
        "Dica de orientação: mostre qual é o objetivo do desafio e a primeira coisa "
        "em que o estudante deve pensar."
    ),
    2: (
        "Dica instrumental: aponte a parte específica do problema que mais importa, "
        "sem dizer a resposta."
    ),
    3: (
        "Dica com exemplo resolvido: resolva passo a passo um problema diferente e menor, "
        "do mesmo tipo, e peça ao estudante para aplicar o mesmo raciocínio. "
        "Nunca use a solução deste desafio."
    ),
}

STRICT_WARNING = (
    "Atenção: a dica anterior revelou a solução e foi descartada. Não cite os textos "
    "da resposta correta; fale só do raciocínio."
)

REVIEW_SYSTEM = (
    "Você revisa desafios de pensamento computacional criados por professores. "
    "Sugira melhorias de clareza, aponte ambiguidades e linguagem pouco adequada à idade "
    "dos estudantes. Não reescreva o desafio inteiro. Responda em português do Brasil, "
    "em no máximo 5 tópicos curtos."
)

# Audience and task criteria from Bebras (Dagienė and Futschek, 2008); options and
# distractors from Haladyna, Downing and Rodriguez (2002). The checkable part is in
# app/domain/draft_rules.py; the rest can only be asked for here.
DRAFT_SYSTEM = (
    "Você cria rascunhos de desafios de pensamento computacional sem código, em português do "
    "Brasil, para estudantes de 14 a 16 anos (faixa Junior do Bebras). "
    "O desafio deve exigir raciocínio de vários passos e poder ser resolvido em cerca de "
    "3 minutos, sem conhecimento prévio de programação: nada que se resolva só de bater o olho. "
    "Use situações reais do cotidiano de um adolescente, com linguagem clara e respeitosa, sem "
    "infantilizar (nada de diminutivos, mascotes ou tom de historinha). "
    "Escreva um enunciado curto que diga exatamente o que fazer, sem entregar a resposta. "
    "Opções e informações erradas devem ser plausíveis, do mesmo tema e baseadas em erros comuns "
    "de raciocínio, nunca absurdas; as opções devem ter forma e tamanho parecidos e só uma pode "
    "estar correta. O estudante pode pedir dicas, então o desafio pode ser exigente. "
    "Responda apenas com um objeto JSON, sem nenhum texto antes ou depois."
)

DRAFT_GUIDANCE = {
    ChallengeType.ORDERING: (
        "Os passos devem depender uns dos outros (cada um usa o resultado de outro), "
        "de modo que só uma ordem funcione."
    ),
    ChallengeType.GROUPING: (
        "Cada item deve pertencer a uma única etapa por um motivo que exija pensar, "
        "não por uma palavra repetida."
    ),
    ChallengeType.FILTERING: (
        "As informações irrelevantes devem parecer úteis à primeira vista, e a pergunta deve "
        "exigir combinar as relevantes."
    ),
    ChallengeType.PATTERN: (
        "A regra deve combinar duas operações, alternar ou depender da posição; as opções "
        "erradas devem vir de regras parecidas, porém erradas."
    ),
}

_DRAFT_SHAPES = {
    ChallengeType.ORDERING: {
        "items": [{"id": "a", "text": "..."}, {"id": "b", "text": "..."}],
        "solution": ["b", "a"],
    },
    ChallengeType.GROUPING: {
        "groups": [{"id": "g1", "text": "..."}, {"id": "g2", "text": "..."}],
        "items": [{"id": "a", "text": "..."}, {"id": "b", "text": "..."}],
        "solution": {"a": "g1", "b": "g2"},
    },
    ChallengeType.FILTERING: {
        "question": "...",
        "items": [{"id": "a", "text": "..."}, {"id": "b", "text": "..."}],
        "solution": ["a"],
    },
    ChallengeType.PATTERN: {
        "sequence": ["...", "...", "..."],
        "options": [{"id": "a", "text": "..."}, {"id": "b", "text": "..."}],
        "solution": "a",
    },
}


def _texts(elements: list[dict]) -> dict[str, str]:
    return {element["id"]: element["text"] for element in elements}


def _listing(title: str, elements: list[dict]) -> list[str]:
    # Texts only: students see per-student ids, so a stored id in a hint would mislead.
    return [f"{title}:"] + [f"- {e['text']}" for e in elements]


def render_content(challenge_type: str, content: dict) -> str:
    """The challenge content as text, with the solution written with item texts."""
    lines: list[str] = []
    if challenge_type == ChallengeType.ORDERING:
        items = _texts(content["items"])
        lines += _listing("Itens", content["items"])
        lines.append("Solução (ordem correta):")
        lines += [f"{n}. {items[i]}" for n, i in enumerate(content["solution"], start=1)]
    elif challenge_type == ChallengeType.GROUPING:
        items, groups = _texts(content["items"]), _texts(content["groups"])
        lines += _listing("Etapas", content["groups"]) + _listing("Itens", content["items"])
        lines.append("Solução (item → etapa):")
        lines += [f"- {items[i]} → {groups[g]}" for i, g in content["solution"].items()]
    elif challenge_type == ChallengeType.FILTERING:
        items = _texts(content["items"])
        lines.append(f"Pergunta: {content['question']}")
        lines += _listing("Itens", content["items"])
        relevant = "; ".join(items[i] for i in content["solution"])
        lines.append(f"Solução: Itens relevantes: {relevant}")
    else:
        options = _texts(content["options"])
        lines.append("Sequência: " + ", ".join(content["sequence"]))
        lines += _listing("Opções", content["options"])
        lines.append(f"Solução: Resposta correta: {options[content['solution']]}")
    return "\n".join(lines)


def render_answer(challenge_type: str, content: dict, answer: dict) -> str:
    """A student's (already validated) answer written with item texts, not ids."""
    if challenge_type == ChallengeType.ORDERING:
        items = _texts(content["items"])
        return "Ordem enviada: " + " → ".join(items[i] for i in answer["order"])
    if challenge_type == ChallengeType.GROUPING:
        items, groups = _texts(content["items"]), _texts(content["groups"])
        pairs = [f"- {items[i]} → {groups[g]}" for i, g in answer["assignment"].items()]
        return "\n".join(["Etapas escolhidas:", *pairs])
    if challenge_type == ChallengeType.FILTERING:
        items = _texts(content["items"])
        selected = "; ".join(items[i] for i in answer["selected"]) or "nenhum item marcado"
        return f"Itens marcados: {selected}"
    return f"Opção escolhida: {_texts(content['options'])[answer['option']]}"


def _type_line(challenge_type: str) -> str:
    return f"Tipo: {challenge_type} ({SKILL_LABELS[challenge_type]})"


def _bullets(title: str, lines: list[str]) -> list[str]:
    return [f"{title}:"] + [f"- {line}" for line in lines]


def hint_prompt(
    challenge: ChallengeDraft,
    level: int,
    previous_hints: list[str],
    answer: dict | None = None,
    strict: bool = False,
) -> Prompt:
    lines = [
        _type_line(challenge.type),
        f"Enunciado: {challenge.statement}",
        render_content(challenge.type, challenge.content),
        f"Nível da dica: {level}",
        LEVEL_INSTRUCTIONS[level],
    ]
    if previous_hints:
        lines += _bullets("Dicas já mostradas (não repita)", previous_hints)
    else:
        lines.append("Dicas já mostradas: nenhuma.")
    if answer is not None:
        lines.append("Resposta enviada pelo estudante (errada):")
        lines.append(render_answer(challenge.type, challenge.content, answer))
    if strict:
        lines.append(STRICT_WARNING)
    return Prompt(HINT_SYSTEM, "\n".join(lines))


def review_prompt(challenge: ChallengeDraft) -> Prompt:
    lines = [
        _type_line(challenge.type),
        f"Título: {challenge.title}",
        f"Enunciado: {challenge.statement}",
        render_content(challenge.type, challenge.content),
        f"Explicação: {challenge.explanation or '(sem explicação)'}",
        *_bullets("Regras do modelo", template_rules(challenge.type)),
    ]
    return Prompt(REVIEW_SYSTEM, "\n".join(lines))


def _example_json(example: ChallengeDraft) -> str:
    fields = {
        "title": example.title,
        "statement": example.statement,
        "explanation": example.explanation,
        "content": example.content,
    }
    return json.dumps(fields, ensure_ascii=False)


def draft_prompt(
    challenge_type: str,
    topic: str,
    examples: list[ChallengeDraft],
    errors: list[str] | tuple[str, ...] = (),
) -> Prompt:
    challenge_type = ChallengeType(challenge_type)
    shape = {
        "title": "...",
        "statement": "...",
        "explanation": "...",
        "content": _DRAFT_SHAPES[challenge_type],
    }
    lines = [
        f"Tipo: {challenge_type.value}",
        f"Habilidade: {SKILL_LABELS[challenge_type]}. {SKILL_DESCRIPTIONS[challenge_type]}",
        f"Tema: {topic}",
        DRAFT_GUIDANCE[challenge_type],
        *_bullets("Regras do modelo", template_rules(challenge_type)),
        *_bullets("Regras de dificuldade (conferidas pelo sistema)", draft_rules(challenge_type)),
        "Formato JSON esperado (o conteúdo segue o tipo):",
        json.dumps(shape, ensure_ascii=False),
    ]
    if examples:
        lines.append("Exemplos publicados pelo professor (mesmo tipo):")
        lines += [_example_json(example) for example in examples]
    if errors:
        lines += _bullets("A resposta anterior tinha estes erros, corrija-os", list(errors))
    return Prompt(DRAFT_SYSTEM, "\n".join(lines))
