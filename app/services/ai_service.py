import json
import logging
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.ports import LLMClient, LLMError
from app.domain.challenge_types import (
    ChallengeDraft,
    ChallengeType,
    assign_item_ids,
    challenge_errors,
)
from app.domain.content import draft_topic_errors
from app.domain.draft_rules import draft_rule_errors
from app.domain.enums import HintSource, Origin
from app.domain.hint_leak import hint_reveals_solution
from app.domain.hints import cooldown_left, hint_level
from app.infra.db.models import Challenge
from app.infra.repositories.challenges import ChallengeRepository
from app.infra.repositories.hints import HintRepository
from app.infra.repositories.missions import MissionRepository
from app.infra.repositories.submissions import SubmissionRepository
from app.services.content_service import ChallengeView, ContentService, draft_of
from app.services.exceptions import (
    Conflict,
    NotFound,
    RateLimited,
    ServiceUnavailable,
    ValidationFailed,
)
from app.services.prompts import (
    Prompt,
    draft_prompt,
    hint_prompt,
    review_prompt,
)

logger = logging.getLogger(__name__)

HINT_MAX_TOKENS = 1000
REVIEW_MAX_TOKENS = 1500
DRAFT_MAX_TOKENS = 1200
DRAFT_ATTEMPTS = 2

FALLBACK_HINTS = {
    ChallengeType.ORDERING: {
        1: "Leia o enunciado de novo: qual é o objetivo final? Que passo precisa vir antes de "
        "todos os outros?",
        2: "Escolha um par de passos e pergunte: algum depende do outro já estar pronto? "
        "Qual deve vir antes?",
        3: "Para ir à escola, primeiro você acorda, depois se veste e só então sai de casa. "
        "Quais passos do desafio também dependem de outro já estar feito?",
    },
    ChallengeType.GROUPING: {
        1: "Olhe para cada etapa e pense no que ela precisa realizar. Que tipo de tarefa "
        "combina com cada uma?",
        2: "Pegue uma tarefa por vez e pergunte em qual etapa ela ajuda a chegar ao objetivo. "
        "Alguma etapa ficou sem tarefas?",
        3: "Numa festa, comprar balões faz parte de preparar, e cortar o bolo faz parte da "
        "festa em si. Em que momento acontece cada tarefa do desafio?",
    },
    ChallengeType.FILTERING: {
        1: "Releia a pergunta com atenção: o que exatamente ela quer saber? Quais informações "
        "ajudam a responder isso?",
        2: "Para cada informação, pergunte: se ela sumisse, eu ainda conseguiria responder? "
        "Quais são indispensáveis?",
        3: "Para saber se dá tempo de ver um filme, importam o horário de início e a duração, "
        "não a cor da poltrona. Quais informações do desafio mudam a resposta?",
    },
    ChallengeType.PATTERN: {
        1: "Compare cada termo com o anterior: o que mudou de um para o outro? Essa mudança "
        "se repete?",
        2: "Descubra a regra que transforma um termo no seguinte e teste-a em todos os pares. "
        "Ela funciona sempre?",
        3: "Em círculo, quadrado, círculo, quadrado, a regra é alternar, então o próximo é "
        "círculo. Qual regra se repete na sequência do desafio?",
    },
}

# Last resort when a fixed fallback happens to contain the answer of this challenge.
NEUTRAL_HINT = "Releia o enunciado com calma. Qual é o objetivo do desafio?"

FALLBACK_SUGGESTIONS = (
    "Não foi possível obter sugestões da IA agora. As regras do modelo foram conferidas "
    "normalmente; tente a revisão de novo mais tarde."
)

_CODE_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


@dataclass(frozen=True)
class HintResult:
    hint: str
    level: int
    cooldown_seconds: int


@dataclass(frozen=True)
class Review:
    rule_violations: list[str]
    suggestions: str


def _parse_draft(challenge_type: str, reply: str) -> tuple[ChallengeDraft | None, list[str]]:
    """Turn the model's JSON into a draft; the errors go back to the model on the retry."""
    text = reply.strip()
    fenced = _CODE_FENCE.match(text)
    if fenced:
        text = fenced.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None, ["A resposta da IA não é um JSON válido."]
    if not isinstance(data, dict) or not isinstance(data.get("content"), dict):
        return None, ["O JSON precisa ter os campos title, statement, explanation e content."]
    draft = ChallengeDraft(
        title=data.get("title"),
        statement=data.get("statement"),
        type=challenge_type,
        content=assign_item_ids(challenge_type, data["content"]),
        explanation=data.get("explanation") or None,
    )
    # The draft rules expect content that already passes the template rules.
    return draft, challenge_errors(draft) or draft_rule_errors(draft)


class AIService:
    """Hints for students and review/draft support for professors."""

    def __init__(
        self,
        session: Session,
        clock: Clock,
        llm: LLMClient,
        content: ContentService,
        cooldown_seconds: int,
    ) -> None:
        self.session = session
        self.clock = clock
        self.llm = llm
        self.content = content
        self.cooldown_seconds = cooldown_seconds
        self.hints = HintRepository(session)
        self.missions = MissionRepository(session)
        self.challenges = ChallengeRepository(session)
        self.submissions = SubmissionRepository(session)

    # Student hints

    def cooldown_seconds_left(self, user_id: int, challenge_id: int) -> int:
        usage = self.hints.requested_hints(user_id, challenge_id)
        return cooldown_left(usage.last_shown_at, self.clock.now(), self.cooldown_seconds)

    def request_hint(self, user_id: int, challenge_id: int) -> HintResult:
        if challenge_id not in self.missions.visible_published_challenge_ids(user_id):
            raise NotFound("challenge_not_found", "Desafio não encontrado.")
        if self.submissions.has_solved(user_id, challenge_id):
            raise Conflict("already_solved", "Você já resolveu este desafio.")
        usage = self.hints.requested_hints(user_id, challenge_id)
        now = self.clock.now()
        wait = cooldown_left(usage.last_shown_at, now, self.cooldown_seconds)
        if wait > 0:
            raise RateLimited(
                "hint_cooldown", "Aguarde alguns segundos para pedir outra dica.", retry_after=wait
            )

        challenge = self.challenges.get(challenge_id)
        level = hint_level(usage.count)
        text, discarded = self._safe_hint(user_id, challenge, level)
        self.hints.add(user_id, challenge_id, HintSource.REQUEST, level, text, discarded, now)
        self.session.commit()
        return HintResult(hint=text, level=level, cooldown_seconds=self.cooldown_seconds)

    def hint_after_wrong(self, user_id: int, challenge: Challenge, answer: dict) -> str | None:
        """Level-1 hint for the first wrong answer; the caller commits."""
        if self.hints.after_wrong_hint_exists(user_id, challenge.id):
            return None
        text, discarded = self._safe_hint(user_id, challenge, 1, answer)
        self.hints.add(
            user_id, challenge.id, HintSource.AFTER_WRONG, 1, text, discarded, self.clock.now()
        )
        return text

    def _safe_hint(
        self, user_id: int, challenge: Challenge, level: int, answer: dict | None = None
    ) -> tuple[str, int]:
        """A hint that passed the leak check, or the fallback; also how many were discarded."""
        previous = self.hints.shown_texts(user_id, challenge.id)
        discarded = 0
        for strict in (False, True):
            prompt = hint_prompt(draft_of(challenge), level, previous, answer, strict)
            reply = self._ask(prompt, HINT_MAX_TOKENS)
            if reply is None:
                break
            if not hint_reveals_solution(challenge.type, challenge.content, reply):
                return reply, discarded
            discarded += 1
        fallback = FALLBACK_HINTS[challenge.type][level]
        if hint_reveals_solution(challenge.type, challenge.content, fallback):
            fallback = NEUTRAL_HINT
        return fallback, discarded

    def _ask(self, prompt: Prompt, max_tokens: int) -> str | None:
        """The model's reply, or None when it failed or said nothing."""
        try:
            reply = self.llm.complete(prompt.system, prompt.user, max_tokens=max_tokens)
        except LLMError as error:
            logger.warning("LLM call failed: %s", error)
            return None
        if not reply.strip():
            logger.warning("LLM returned an empty reply")
            return None
        return reply.strip()

    # Professor support

    def review(self, professor_id: int, challenge_id: int) -> Review:
        draft = self.content.get_draft(professor_id, challenge_id)
        suggestions = self._ask(review_prompt(draft), REVIEW_MAX_TOKENS)
        return Review(challenge_errors(draft), suggestions or FALLBACK_SUGGESTIONS)

    def draft(
        self, professor_id: int, challenge_type: str, topic: str, mission_id: int | None
    ) -> ChallengeView:
        errors = draft_topic_errors(topic)
        if challenge_type not in set(ChallengeType):
            errors.append("Tipo de desafio inválido.")
        if errors:
            raise ValidationFailed(errors=errors)
        if mission_id is not None:
            self.content.get_mission(professor_id, mission_id)  # 404 before paying for a call
        examples = self.challenges.published_examples(professor_id, ChallengeType(challenge_type))
        texts = [draft_of(example) for example in examples]

        errors = []
        for _ in range(DRAFT_ATTEMPTS):
            prompt = draft_prompt(challenge_type, topic.strip(), texts, errors)
            try:
                reply = self.llm.complete(prompt.system, prompt.user, max_tokens=DRAFT_MAX_TOKENS)
            except LLMError as error:
                logger.warning("LLM call failed: %s", error)
                raise ServiceUnavailable(
                    "ai_unavailable", "A IA não está disponível agora. Tente de novo mais tarde."
                ) from error
            draft, errors = _parse_draft(challenge_type, reply)
            if not errors:
                return self.content.create_challenge(
                    professor_id, draft, origin=Origin.AI, mission_id=mission_id
                )
        raise ValidationFailed(
            "invalid_draft", "A IA não gerou um rascunho válido. Tente outro tema.", errors=errors
        )
