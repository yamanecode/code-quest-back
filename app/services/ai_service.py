import json
import logging
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.ports import LLMClient, LLMError, LLMLimitReached
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
from app.domain.hints import cooldown_left, hint_level, pick_variant
from app.infra.db.models import Challenge
from app.infra.repositories.challenges import ChallengeRepository
from app.infra.repositories.hints import HintRepository, HintUsage
from app.infra.repositories.locks import lock_user
from app.infra.repositories.missions import MissionRepository
from app.infra.repositories.submissions import SubmissionRepository
from app.services.content_service import ChallengeView, ContentService, draft_of
from app.services.exceptions import (
    NotFound,
    RateLimited,
    ServiceUnavailable,
    ValidationFailed,
)
from app.services.guards import already_solved
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
# Seconds: a student waits for a hint and a professor for a review; a draft is longer.
HINT_TIMEOUT_SECONDS = 10
REVIEW_TIMEOUT_SECONDS = 10
DRAFT_TIMEOUT_SECONDS = 30

# Generic per type, never about one challenge. Level 1 is also the pool of the automatic hint.
# Each pool has several variants so the same sentence is not shown twice in a row.
FALLBACK_HINTS: dict[ChallengeType, dict[int, tuple[str, ...]]] = {
    ChallengeType.ORDERING: {
        1: (
            "Leia o enunciado de novo: qual é o objetivo final? Que passo precisa vir antes de "
            "todos os outros?",
            "Pense no resultado final. Qual passo só faz sentido depois de todos os outros, e "
            "qual não precisa de nenhum antes dele?",
        ),
        2: (
            "Escolha um par de passos e pergunte: algum depende do outro já estar pronto? "
            "Qual deve vir antes?",
            "Pegue dois passos vizinhos e troque-os de lugar na cabeça. A sequência ainda "
            "funciona? Se não, qual dos dois precisa vir primeiro?",
        ),
        3: (
            "Para ir à escola, primeiro você acorda, depois se veste e só então sai de casa. "
            "Quais passos do desafio também dependem de outro já estar feito?",
            "Num sanduíche, o pão vem antes do recheio e comer fica por último. Comece pelo "
            "passo que não depende de nada e pelo que só pode ser o final. Que passos do "
            "desafio ficam no meio, entre esses dois?",
            "Em molhar o cabelo, passar xampu e enxaguar, cada passo só faz sentido depois do "
            "anterior. Que passos do desafio só fazem sentido depois de outro?",
        ),
    },
    ChallengeType.GROUPING: {
        1: (
            "Olhe para cada grupo e pense no que ele representa. Que tipo de tarefa combina "
            "com cada um?",
            "Antes de distribuir, imagine uma tarefa que claramente pertence a cada grupo. "
            "Quais tarefas do desafio se parecem com ela?",
        ),
        2: (
            "Pegue uma tarefa por vez e pergunte a qual grupo ela ajuda mais. Algum grupo "
            "ficou sem tarefas?",
            "Comece pelas tarefas mais fáceis de encaixar; as que sobrarem ficam mais fáceis "
            "de decidir. No fim, algum grupo ficou vazio?",
        ),
        3: (
            "Numa festa, comprar balões faz parte de preparar, e cortar o bolo faz parte da "
            "festa em si. A qual grupo do desafio cada tarefa se parece mais?",
            "Num trabalho escolar, pesquisar o tema ajuda a produzir a pesquisa e montar os "
            "slides ajuda a produzir a apresentação. Que resultado cada tarefa do desafio "
            "ajuda a produzir?",
            "Se uma tarefa parece caber em dois grupos, qual deles ficaria incompleto sem ela?",
        ),
    },
    ChallengeType.FILTERING: {
        1: (
            "Releia a pergunta com atenção: o que exatamente ela quer saber? Quais informações "
            "ajudam a responder isso?",
            "Imagine a resposta já escrita. Quais informações você teria usado para chegar a ela?",
        ),
        2: (
            "Para cada informação, pergunte: se ela sumisse, eu ainda conseguiria responder? "
            "Quais são indispensáveis?",
            "Separe as informações em duas colunas: as que mudam a resposta e as que só "
            "enfeitam. Em qual coluna cada uma entra?",
        ),
        3: (
            "Para saber quantas pizzas pedir para 8 pessoas, a conta usa o número de pessoas "
            "e as fatias de cada uma; sabor e marca não entram. Que informações do desafio "
            "entrariam na sua conta?",
            "Para saber se dá tempo de ver um filme, importam o horário de início e a "
            "duração, não a cor da poltrona. Quais informações do desafio mudam a resposta?",
            "Uma informação pode parecer inútil e ser necessária, ou parecer importante e não "
            "servir. Testando cada uma contra a pergunta, e não contra o assunto, quais sobram?",
        ),
    },
    ChallengeType.PATTERN: {
        1: (
            "Compare cada termo com o anterior: o que mudou de um para o outro? Essa mudança "
            "se repete?",
            "Escreva a diferença entre cada par de termos seguidos. Ela é sempre igual? Se "
            "não, ela mesma segue alguma regra?",
        ),
        2: (
            "Descubra a regra que transforma um termo no seguinte e teste-a em todos os pares. "
            "Ela funciona sempre?",
            "Se a regra falha em algum par, talvez a sequência tenha duas regras alternadas, "
            "uma nas posições ímpares e outra nas pares, ou use os dois termos anteriores. "
            "Qual dessas ideias funciona?",
        ),
        3: (
            "Em círculo, quadrado, círculo, quadrado, a regra é alternar, então o próximo é "
            "círculo. Qual regra se repete na sequência do desafio?",
            "Em 1, 2, 4, 7 a regra está nas diferenças: +1, +2, +3. Que regra aparece nas "
            "diferenças da sequência do desafio?",
            "Em 1, 3, 2, 4, 3, 5 os números sobem e descem, mas olhando só os de posição "
            "ímpar e só os de posição par aparece uma regra simples em cada grupo. Isso "
            "ajuda aqui?",
        ),
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


def _log_failure(error: LLMError) -> None:
    # The daily limit is logged once per day by the client that enforces it.
    if not isinstance(error, LLMLimitReached):
        logger.warning("LLM call failed: %s", error)


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

    # Both hint paths: short check under the user lock, commit (which releases the lock),
    # call the model with no lock held, then lock again, check again and store or drop.

    def request_hint(self, user_id: int, challenge_id: int) -> HintResult:
        lock_user(self.session, user_id)
        if challenge_id not in self.missions.visible_published_challenge_ids(user_id):
            raise NotFound("challenge_not_found", "Desafio não encontrado.")
        if self.submissions.has_solved(user_id, challenge_id):
            raise already_solved()
        usage = self.hints.requested_hints(user_id, challenge_id)
        self._check_cooldown(usage)
        level = hint_level(usage.count)
        draft = draft_of(self.challenges.get(challenge_id))
        previous = self.hints.shown_texts(user_id, challenge_id)
        self.session.commit()

        text, discarded = self._safe_hint(draft, level, previous)

        lock_user(self.session, user_id)
        # A parallel request may have shown a hint while this one waited for the model.
        self._check_cooldown(self.hints.requested_hints(user_id, challenge_id))
        self.hints.add(
            user_id, challenge_id, HintSource.REQUEST, level, text, discarded, self.clock.now()
        )
        self.session.commit()
        return HintResult(hint=text, level=level, cooldown_seconds=self.cooldown_seconds)

    def hint_after_wrong(self, user_id: int, challenge: Challenge, answer: dict) -> str | None:
        """Level-1 hint for the first wrong answer; runs after the submission is committed."""
        challenge_id = challenge.id
        if self.hints.after_wrong_hint_exists(user_id, challenge_id):
            return None
        draft = draft_of(challenge)
        previous = self.hints.shown_texts(user_id, challenge_id)
        self.session.commit()

        text, discarded = self._safe_hint(draft, 1, previous, answer)

        lock_user(self.session, user_id)
        if self.hints.after_wrong_hint_exists(user_id, challenge_id):
            # A parallel wrong answer stored its hint first; only one is ever shown.
            self.session.commit()
            return None
        self.hints.add(
            user_id, challenge_id, HintSource.AFTER_WRONG, 1, text, discarded, self.clock.now()
        )
        self.session.commit()
        return text

    def _check_cooldown(self, usage: HintUsage) -> None:
        wait = cooldown_left(usage.last_shown_at, self.clock.now(), self.cooldown_seconds)
        if wait > 0:
            raise RateLimited(
                "hint_cooldown", "Aguarde alguns segundos para pedir outra dica.", retry_after=wait
            )

    def _safe_hint(
        self, draft: ChallengeDraft, level: int, previous: list[str], answer: dict | None = None
    ) -> tuple[str, int]:
        """A hint that passed the leak check, or the fallback; also how many were discarded.

        Touches no database: it runs while no transaction is open.
        """
        discarded = 0
        for strict in (False, True):
            prompt = hint_prompt(draft, level, previous, answer, strict)
            reply = self._ask(prompt, HINT_MAX_TOKENS, HINT_TIMEOUT_SECONDS)
            if reply is None:
                break
            if not hint_reveals_solution(draft.type, draft.content, reply):
                return reply, discarded
            discarded += 1
        safe = tuple(
            text
            for text in FALLBACK_HINTS[draft.type][level]
            if not hint_reveals_solution(draft.type, draft.content, text)
        )
        return (pick_variant(safe, previous) if safe else NEUTRAL_HINT), discarded

    def _ask(self, prompt: Prompt, max_tokens: int, timeout_seconds: float) -> str | None:
        """The model's reply, or None when it failed or said nothing."""
        try:
            reply = self.llm.complete(
                prompt.system, prompt.user, max_tokens=max_tokens, timeout_seconds=timeout_seconds
            )
        except LLMError as error:
            _log_failure(error)
            return None
        if not reply.strip():
            logger.warning("LLM returned an empty reply")
            return None
        return reply.strip()

    # Professor support

    def review(self, professor_id: int, challenge_id: int) -> Review:
        draft = self.content.get_draft(professor_id, challenge_id)
        suggestions = self._ask(review_prompt(draft), REVIEW_MAX_TOKENS, REVIEW_TIMEOUT_SECONDS)
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
                reply = self.llm.complete(
                    prompt.system,
                    prompt.user,
                    max_tokens=DRAFT_MAX_TOKENS,
                    timeout_seconds=DRAFT_TIMEOUT_SECONDS,
                )
            except LLMError as error:
                _log_failure(error)
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
