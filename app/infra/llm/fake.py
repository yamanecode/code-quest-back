import json
import re
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from app.core.ports import LLMError
from app.domain.challenge_types import TITLE_MAX, ChallengeType

SAFE_HINT = "Dica nível {level}: pense no que precisa acontecer primeiro. Qual seria?"
FAKE_REVIEW = (
    "Sugestões: o enunciado está claro. Confira se as palavras são adequadas à idade "
    "da turma e se existe só uma resposta correta."
)

_DRAFT_CONTENT = {
    ChallengeType.ORDERING: {
        "items": [
            {"id": "a", "text": "Separar o material"},
            {"id": "b", "text": "Seguir as instruções"},
            {"id": "c", "text": "Conferir o resultado"},
        ],
        "solution": ["a", "b", "c"],
    },
    ChallengeType.GROUPING: {
        "groups": [{"id": "g1", "text": "Preparar"}, {"id": "g2", "text": "Executar"}],
        "items": [
            {"id": "a", "text": "Ler o pedido"},
            {"id": "b", "text": "Juntar o material"},
            {"id": "c", "text": "Montar as peças"},
            {"id": "d", "text": "Testar o resultado"},
        ],
        "solution": {"a": "g1", "b": "g1", "c": "g2", "d": "g2"},
    },
    ChallengeType.FILTERING: {
        "question": "Quais informações ajudam a resolver o problema?",
        "items": [
            {"id": "a", "text": "O horário de início"},
            {"id": "b", "text": "A cor da mochila"},
            {"id": "c", "text": "A duração da tarefa"},
            {"id": "d", "text": "O nome do cachorro"},
        ],
        "solution": ["a", "c"],
    },
    ChallengeType.PATTERN: {
        "sequence": ["1", "3", "5", "7"],
        "options": [
            {"id": "a", "text": "9"},
            {"id": "b", "text": "8"},
            {"id": "c", "text": "10"},
            {"id": "d", "text": "11"},
        ],
        "solution": "a",
    },
}


@dataclass(frozen=True)
class RecordedPrompt:
    system: str
    user: str


class FakeLLMClient:
    """Stand-in for a real model.

    With `replies` it returns them in order (an exception in the list is raised) and fails
    once they run out. Without `replies` it answers deterministically (server mode).
    Every prompt is recorded; with `log_path` it is also appended to that file as JSON lines.

    Server mode tells the features apart by the lines the prompt builders write
    ("Tema:" for drafts, "Nível da dica:" for hints, anything else is a review).
    Triggers: "[fake:error]" anywhere fails the call, "[fake:leak]" makes a hint echo the
    prompt (which holds the solution) and "[fake:invalid]" makes a draft that is not JSON.
    """

    def __init__(
        self, replies: Iterable[str | Exception] | None = None, log_path: str | None = None
    ) -> None:
        self.scripted = replies is not None
        self.replies = deque(replies or [])
        self.log_path = log_path
        self.prompts: list[RecordedPrompt] = []

    def complete(self, system: str, user: str, *, max_tokens: int) -> str:
        self.prompts.append(RecordedPrompt(system, user))
        if self.log_path:
            line = json.dumps({"system": system, "user": user}, ensure_ascii=False)
            with Path(self.log_path).open("a", encoding="utf-8") as log:
                log.write(line + "\n")
        if self.scripted:
            return self._next_reply()
        return self._server_reply(user)

    def _server_reply(self, user: str) -> str:
        if "[fake:error]" in user:
            raise LLMError("fake error trigger")
        topic = re.search(r"^Tema: (.+)$", user, re.MULTILINE)
        if topic:
            challenge_type = re.search(r"^Tipo: (\w+)", user, re.MULTILINE).group(1)
            return _draft(ChallengeType(challenge_type), topic.group(1))
        level = re.search(r"^Nível da dica: (\d+)$", user, re.MULTILINE)
        if level:
            if "[fake:leak]" in user:
                return user
            return SAFE_HINT.format(level=level.group(1))
        return FAKE_REVIEW

    def _next_reply(self) -> str:
        if not self.replies:
            raise LLMError("no scripted reply left")
        reply = self.replies.popleft()
        if isinstance(reply, Exception):
            raise reply
        return reply


def _draft(challenge_type: ChallengeType, topic: str) -> str:
    if "[fake:invalid]" in topic:
        return "Aqui está o desafio que você pediu (sem JSON)."
    draft = {
        "title": f"Rascunho: {topic}"[:TITLE_MAX].strip(),
        "statement": f"Desafio sobre {topic}. Leia com atenção e use o raciocínio pedido.",
        "explanation": "Rascunho criado para o professor revisar.",
        "content": _DRAFT_CONTENT[challenge_type],
    }
    return json.dumps(draft, ensure_ascii=False)
